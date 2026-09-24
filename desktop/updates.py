"""Small, fail-silent update checker for GitHub Releases."""

from __future__ import annotations

import json
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi

from .version import APP_VERSION

LATEST_RELEASE_API = "https://api.github.com/repos/barracol/running-dashboard/releases/latest"
CACHE_FILENAME = "update-check.json"
CACHE_TTL = timedelta(hours=6)


def _version_tuple(value: str) -> tuple[int, ...]:
    clean = value.strip().lower().lstrip("v").split("-", 1)[0]
    try:
        return tuple(int(part) for part in clean.split("."))
    except ValueError:
        return ()


def _result(latest: str = "", release_url: str = "") -> dict:
    current = _version_tuple(APP_VERSION)
    remote = _version_tuple(latest)
    return {
        "current_version": APP_VERSION,
        "latest_version": latest.lstrip("v"),
        "available": bool(current and remote and remote > current),
        "release_url": release_url if release_url.startswith("https://github.com/barracol/running-dashboard/") else "",
    }


def check_for_update(data_dir: Path, force: bool = False) -> dict:
    cache = data_dir / CACHE_FILENAME
    if not force:
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            checked_at = datetime.fromisoformat(cached["checked_at"])
            if datetime.now(timezone.utc) - checked_at < CACHE_TTL:
                return _result(cached.get("latest_version", ""), cached.get("release_url", ""))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            pass
    try:
        request = Request(
            LATEST_RELEASE_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": f"RunningDashboard/{APP_VERSION}"},
        )
        context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(request, timeout=4, context=context) as response:
            payload = json.loads(response.read(250_000).decode("utf-8"))
        latest = str(payload.get("tag_name", ""))
        release_url = str(payload.get("html_url", ""))
        data_dir.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "latest_version": latest,
            "release_url": release_url,
        }, indent=2) + "\n", encoding="utf-8")
        return _result(latest, release_url)
    except (OSError, HTTPError, URLError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return _result()
