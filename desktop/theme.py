"""Editable colour themes for the desktop application."""

from __future__ import annotations

import json
import re
from pathlib import Path

THEME_FILENAME = "theme.json"
PRESETS = {
    "running": {"background":"#0b0d0c","panel":"#141816","surface":"#0e110f","surface_alt":"#202622","line":"#2a312d","muted":"#929c96","text":"#f4f7f5","primary":"#a7f432","secondary":"#43d9c7","warning":"#ff9f43","danger":"#ff6575","glow":"#1a2920"},
    "synopsys": {"background":"#090b18","panel":"#12162a","surface":"#0d1122","surface_alt":"#1b2140","line":"#30385f","muted":"#9ba6c8","text":"#f5f7ff","primary":"#8b5cf6","secondary":"#22d3ee","warning":"#f59e0b","danger":"#fb7185","glow":"#25205a"},
}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

def ensure_theme_file(data_dir: Path) -> Path:
    path = data_dir / THEME_FILENAME
    if not path.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"preset": "running", "colors": {}}, indent=2) + "\n", encoding="utf-8")
    return path

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
    return {
        "enabled": bool(community.get("enabled", preset == "synopsys")),
        "feed_url": str(community.get("feed_url", "https://leobarra.it/data/synopsys-community.json")),
        "name": str(community.get("name", "Synopsys Running Community")),
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
