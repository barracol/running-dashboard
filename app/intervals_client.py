from __future__ import annotations

from base64 import b64encode
from datetime import date
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SPORTS = {
    "Run": "running", "TrailRun": "trail_running", "Walk": "walking", "Hike": "hiking",
    "Ride": "cycling", "VirtualRide": "cycling", "GravelRide": "cycling",
    "MountainBikeRide": "mountain_biking", "Swim": "swimming", "Rowing": "rowing",
    "Kayaking": "kayaking", "AlpineSki": "skiing", "NordicSki": "cross_country_skiing",
    "IceSkate": "skating", "WeightTraining": "workout", "Workout": "workout",
    "Yoga": "yoga", "Soccer": "football", "Tennis": "tennis",
}

class IntervalsError(RuntimeError):
    pass

def configuration() -> dict:
    athlete_id = os.getenv("INTERVALS_ATHLETE_ID", "").strip()
    api_key = os.getenv("INTERVALS_API_KEY", "").strip()
    return {"configured": bool(athlete_id and api_key), "athlete_id": athlete_id or None}

def _request(path: str, params: dict | None = None) -> object:
    athlete_id = os.getenv("INTERVALS_ATHLETE_ID", "").strip()
    api_key = os.getenv("INTERVALS_API_KEY", "").strip()
    if not athlete_id or not api_key:
        raise IntervalsError("Intervals.icu non è configurato")
    base_url = os.getenv("INTERVALS_BASE_URL", "https://intervals.icu/api/v1").strip().rstrip("/")
    if not base_url.startswith("https://") and "localhost" not in base_url:
        raise IntervalsError("INTERVALS_BASE_URL deve usare HTTPS")
    url = f"{base_url}{path}" + (("?" + urlencode(params)) if params else "")
    token = b64encode(f"API_KEY:{api_key}".encode()).decode()
    request = Request(url, headers={"Authorization": f"Basic {token}", "Accept": "application/json", "User-Agent": "RunningDashboard/0.1"})
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise IntervalsError("Credenziali Intervals.icu non valide o accesso negato") from exc
        raise IntervalsError(f"Intervals.icu ha risposto con HTTP {exc.code}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise IntervalsError("Intervals.icu non è raggiungibile o ha restituito dati non validi") from exc

def list_activities(oldest: date, newest: date) -> list[dict]:
    athlete_id = os.environ["INTERVALS_ATHLETE_ID"].strip()
    payload = _request(f"/athlete/{athlete_id}/activities", {"oldest": oldest.isoformat(), "newest": newest.isoformat(), "limit": 1000})
    if not isinstance(payload, list):
        raise IntervalsError("Risposta attività Intervals.icu non valida")
    return [normalize_activity(item) for item in payload if isinstance(item, dict) and item.get("id")]

def normalize_activity(item: dict) -> dict:
    start = str(item.get("start_date_local") or item.get("start_date") or "")
    duration = item.get("moving_time") or item.get("elapsed_time") or 0
    distance = item.get("distance") or 0
    return {
        "external_id": str(item.get("id")), "activity_date": start[:10],
        "activity_name": str(item.get("name") or "Attività Intervals.icu")[:200],
        "activity_type": SPORTS.get(str(item.get("type") or ""), "other"),
        "intervals_type": item.get("type"), "source_name": item.get("source"),
        "distance_m": max(0, round(float(distance))), "duration_s": max(1, round(float(duration))),
        "elapsed_s": round(float(item.get("elapsed_time") or duration or 0)) or None,
        "calories": round(float(item["calories"])) if item.get("calories") is not None else None,
        "avg_heart_rate": round(float(item["average_heartrate"])) if item.get("average_heartrate") is not None else None,
    }
