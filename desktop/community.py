"""Community feed validation, namespaced offline cache and preferences."""
from __future__ import annotations
import json
import ssl
from datetime import date
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import certifi

DEFAULT_FEED_URL = "https://leobarra.it/data/running-community.json"
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
    for key in ("time", "meeting_point", "location", "sport", "pace", "duration", "notes"):
        if item.get(key) is not None: result[key] = str(item[key])[:1000]
    for key in ("website", "registration_url"):
        value = str(item.get(key, ""))[:1000]
        if value and urlparse(value).scheme in {"http", "https"}: result[key] = value
    if isinstance(item.get("distance_km"), (int, float)) and 0 < item["distance_km"] < 1000: result["distance_km"] = item["distance_km"]
    return result

def _validate_feed(payload) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list): raise ValueError("Community feed non valido")
    events = [event for item in payload["events"] if (event := _valid_event(item))]
    return {"name": str(payload.get("name", "Running Community"))[:100], "updated_at": str(payload.get("updated_at", ""))[:40], "events": sorted(events, key=lambda item: (item["date"], item["title"]))}

def _safe_namespace(value: str) -> str:
    clean = "".join(char for char in value.lower() if char.isalnum() or char in "-_").strip("-_")
    return clean[:80] or "community"

def fetch_feed(data_dir: Path, url: str = DEFAULT_FEED_URL, namespace: str = "community") -> tuple[dict, bool]:
    cache = data_dir / f"{_safe_namespace(namespace)}-cache.json"
    try:
        request = Request(url, headers={"User-Agent": "RunningDashboard/0.1"})
        context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(request, timeout=5, context=context) as response:
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
        return {"name": "Running Community", "updated_at": "", "events": []}, True

def read_preferences(profile_dir: Path, namespace: str = "community") -> dict[str, str]:
    values = _read_json(profile_dir / f"{_safe_namespace(namespace)}-preferences.json", {})
    if not isinstance(values, dict): return {}
    return {str(key): value for key, value in values.items() if value in ALLOWED_STATES and value != "none"}

def save_preference(profile_dir: Path, event_id: str, state: str, namespace: str = "community") -> dict[str, str]:
    if not event_id or len(event_id) > 120 or state not in ALLOWED_STATES: raise ValueError("Preferenza non valida")
    values = read_preferences(profile_dir, namespace)
    if state == "none": values.pop(event_id, None)
    else: values[event_id] = state
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / f"{_safe_namespace(namespace)}-preferences.json").write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    return values
