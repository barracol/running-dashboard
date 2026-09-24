"""Editable colour themes for the desktop application."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

THEME_FILENAME = "theme.json"
COMMUNITY_PROFILES = {
    "fa224954eefde04a7c0b3adb4579b140d30b1d973a0d5685f6bb036d6afc48da": {
        "preset": "community-violet",
        "id": "running-community",
        "name": "Running Community",
        "feed_url": "https://leobarra.it/data/running-community.json",
    },
    "69d505ea215b95680acfafb143130f256f00a5478a1fa1bb0d7e851ac1deabd6": {
        "preset": "borgorun",
        "id": "borgolavezzaro-runner",
        "name": "BorgolavezzaroRunner",
        "feed_url": "https://leobarra.it/data/borgolavezzaro-runner.json",
    },
}
PRESETS = {
    "running": {"background":"#0b0d0c","panel":"#141816","surface":"#0e110f","surface_alt":"#202622","line":"#2a312d","muted":"#929c96","text":"#f4f7f5","primary":"#a7f432","secondary":"#43d9c7","warning":"#ff9f43","danger":"#ff6575","glow":"#1a2920"},
    "community-violet": {"background":"#090b18","panel":"#12162a","surface":"#0d1122","surface_alt":"#1b2140","line":"#30385f","muted":"#9ba6c8","text":"#f5f7ff","primary":"#8b5cf6","secondary":"#22d3ee","warning":"#f59e0b","danger":"#fb7185","glow":"#25205a"},
    "borgorun": {"background":"#07130d","panel":"#10251a","surface":"#0b1b13","surface_alt":"#1a3524","line":"#31543c","muted":"#9bb7a1","text":"#f1f7ed","primary":"#9bd44e","secondary":"#6fc7b2","warning":"#d8b85a","danger":"#e06b64","glow":"#1f5a38"},
}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

def ensure_theme_file(data_dir: Path) -> Path:
    path = data_dir / THEME_FILENAME
    if not path.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"preset": "running", "colors": {}}, indent=2) + "\n", encoding="utf-8")
    return path

def activate_community_theme(data_dir: Path, access_code: str) -> bool:
    """Unlock the private colour preset without persisting the access code."""
    code_hash = hashlib.sha256(access_code.strip().encode("utf-8")).hexdigest()
    profile = COMMUNITY_PROFILES.get(code_hash)
    if profile is None:
        return False
    path = ensure_theme_file(data_dir)
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        config = {}
    if not isinstance(config, dict):
        config = {}
    config["preset"] = profile["preset"]
    config["community"] = {
        "enabled": True,
        "id": profile["id"],
        "name": profile["name"],
        "feed_url": profile["feed_url"],
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return True

def load_theme(data_dir: Path) -> tuple[str, dict[str, str]]:
    path = ensure_theme_file(data_dir)
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        config = {}
    preset = config.get("preset", "running")
    if preset not in PRESETS:
        preset = "running"
    colors = dict(PRESETS[preset])
    overrides = config.get("colors", {})
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            if key in colors and isinstance(value, str) and _HEX.fullmatch(value):
                colors[key] = value
    return preset, colors

def community_settings(data_dir: Path) -> dict:
    path = ensure_theme_file(data_dir)
    try: config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): config = {}
    preset = config.get("preset", "running")
    community = config.get("community", {}) if isinstance(config.get("community", {}), dict) else {}
    profile = next((item for item in COMMUNITY_PROFILES.values() if item["preset"] == preset), None)
    return {
        "enabled": bool(community.get("enabled", profile is not None)),
        "id": str(community.get("id", profile["id"] if profile else "community")),
        "feed_url": str(community.get("feed_url", profile["feed_url"] if profile else "")),
        "name": str(community.get("name", profile["name"] if profile else "Running Community")),
    }

def theme_css(data_dir: Path) -> str:
    preset, c = load_theme(data_dir)
    return f"""/* Generated from {THEME_FILENAME}; preset: {preset}. */
:root{{--bg:{c['background']}!important;--panel:{c['panel']}!important;--surface:{c['surface']}!important;--surface-alt:{c['surface_alt']}!important;--line:{c['line']}!important;--muted:{c['muted']}!important;--text:{c['text']}!important;--green:{c['primary']}!important;--cyan:{c['secondary']}!important;--orange:{c['warning']}!important;--danger:{c['danger']}!important;--theme-glow:{c['glow']}!important;--ui-focus:{c['primary']}!important;--ui-hub-bg:{c['surface_alt']}!important;--ui-hub-fg:{c['text']}!important;--ui-hub-line:{c['line']}!important}}
body{{background:radial-gradient(circle at 80% 0,var(--theme-glow) 0,transparent 30%),var(--bg)!important;color:var(--text)!important}}
:is(input,textarea,.form-grid select,.month-card,.race-card,.week-day,.coach-workout,.exercise-card){{background:var(--surface)!important}}
:is(button.secondary,.icon,.panel-head select,.toolbar select){{background:var(--surface-alt)!important;color:var(--text)!important}}
.desktop-profile-switch{{background:var(--surface-alt)!important;color:var(--text)!important;border-color:var(--line)!important}}.desktop-profile-switch:hover{{border-color:var(--green)!important}}
body.desktop-login{{background:radial-gradient(circle at 75% 10%,var(--theme-glow),transparent 35%),var(--bg)!important}}.desktop-login .eyebrow,.desktop-login .profile.demo span{{color:var(--green)!important}}.desktop-login .intro,.desktop-login .profile p,.desktop-login .note{{color:var(--muted)!important}}.desktop-login .profile{{border-color:var(--line)!important;background:var(--panel)!important}}.desktop-login .profile.demo{{background:linear-gradient(145deg,var(--theme-glow),var(--panel))!important}}.desktop-login .profile:hover{{border-color:var(--green)!important}}
"""
