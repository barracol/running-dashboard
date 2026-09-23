"""Synopsys community feed, validation, offline cache and local preferences."""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

DEFAULT_FEED_URL = "https://leobarra.it/data/synopsys-community.json"
CACHE_FILENAME = "synopsys-community-cache.json"
PREFERENCES_FILENAME = "community-preferences.json"
ALLOWED_TYPES = {"race", "workout"}
ALLOWED_STATES = {"none", "interested", "attending"}

def _read_json(path: Path, fallback):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return fallback

def _valid_event(item) -> dict | None:
    if not isinstance(item, dict): return None
    event_id, event_type = str(item.get("id", "")).strip(), str(item.get("type", "")).strip()
    title, event_date = str(item.get("title", "")).strip(), str(item.get("date", "")).strip()
    try: date.fromisoformat(event_date)
    except ValueError: return None
    if not event_id or len(event_id) > 120 or event_type not in ALLOWED_TYPES or not title: return None
    result = {"id": event_id, "type": event_type, "title": title[:200], "date": event_date}
    for key in ("time", "meeting_point", "location", "sport", "pace", "notes"):
        if item.get(key) is not None: result[key] = str(item[key])[:1000]
    for key in ("website", "registration_url"):
        value = str(item.get(key, ""))[:1000]
        if value and urlparse(value).scheme in {"http", "https"}: result[key] = value
    if isinstance(item.get("distance_km"), (int, float)) and 0 < item["distance_km"] < 1000: result["distance_km"] = item["distance_km"]
    return result

def _validate_feed(payload) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list): raise ValueError("Community feed non valido")
    events = [event for item in payload["events"] if (event := _valid_event(item))]
    return {"name": str(payload.get("name", "Synopsys Running Community"))[:100], "updated_at": str(payload.get("updated_at", ""))[:40], "events": sorted(events, key=lambda item: (item["date"], item["title"]))}

def fetch_feed(data_dir: Path, url: str = DEFAULT_FEED_URL) -> tuple[dict, bool]:
    cache = data_dir / CACHE_FILENAME
    try:
        request = Request(url, headers={"User-Agent": "RunningDashboard/0.1"})
        with urlopen(request, timeout=5) as response:
            if response.status != 200: raise URLError(f"HTTP {response.status}")
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000: raise ValueError("Community feed troppo grande")
            payload = _validate_feed(json.loads(raw.decode("utf-8")))
        data_dir.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload, False
    except (OSError, URLError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        cached = _read_json(cache, None)
        if cached is not None: return _validate_feed(cached), True
        return {"name": "Synopsys Running Community", "updated_at": "", "events": []}, True

def read_preferences(profile_dir: Path) -> dict[str, str]:
    values = _read_json(profile_dir / PREFERENCES_FILENAME, {})
    if not isinstance(values, dict): return {}
    return {str(key): value for key, value in values.items() if value in ALLOWED_STATES and value != "none"}

def save_preference(profile_dir: Path, event_id: str, state: str) -> dict[str, str]:
    if not event_id or len(event_id) > 120 or state not in ALLOWED_STATES: raise ValueError("Preferenza non valida")
    values = read_preferences(profile_dir)
    if state == "none": values.pop(event_id, None)
    else: values[event_id] = state
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / PREFERENCES_FILENAME).write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    return values
