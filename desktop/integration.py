"""Desktop-only profile selector, editable theme and HomeHub-link replacement."""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, Form, HTTPException, Request
from pydantic import BaseModel
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.datastructures import Headers

from app.config import get_settings, reset_desktop_profile, set_desktop_profile
from .community import fetch_feed, read_preferences, save_preference
from .demo_data import ensure_demo_data
from .theme import community_settings, ensure_theme_file, theme_css


PROFILE_COOKIE = "running_desktop_profile"
LOGIN_PATH = "/desktop-login"
SETTINGS_FILENAME = "desktop-settings.json"
_demo_lock = Lock()
_demo_ready = False

class CommunityPreference(BaseModel):
    event_id: str
    state: str

def _data_dir() -> Path:
    return Path(os.environ.get("RUNNING_DATA_DIR", Path.home() / ".running-dashboard"))


def _desktop_settings() -> dict:
    path = _data_dir() / SETTINGS_FILENAME
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _onboarding_complete() -> bool:
    return _desktop_settings().get("onboarding_complete") is True


def _complete_onboarding() -> None:
    data_dir = _data_dir(); data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / SETTINGS_FILENAME
    settings = _desktop_settings(); settings["onboarding_complete"] = True
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _ensure_demo_once() -> None:
    global _demo_ready
    if _demo_ready:
        return
    with _demo_lock:
        if not _demo_ready:
            ensure_demo_data()
            _demo_ready = True


class DesktopProfileMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        completed = _onboarding_complete()
        headers = Headers(scope=scope)
        profile = headers.get("cookie", "")
        profile = next((part.split("=", 1)[1] for part in profile.split("; ") if part.startswith(f"{PROFILE_COOKIE}=")), "")
        if completed:
            profile = "user"
            if path == LOGIN_PATH:
                return await RedirectResponse("/", status_code=303)(scope, receive, send)

        if path == "/static/hub-link.js":
            script = "" if completed else _profile_switch_script()
            return await Response(script, media_type="application/javascript")(scope, receive, send)
        if path == "/static/ui-standard.js":
            return await Response(_desktop_ui_script(), media_type="application/javascript")(scope, receive, send)
        if path == "/static/desktop-theme.css":
            return await Response(theme_css(_data_dir()), media_type="text/css", headers={"Cache-Control": "no-store"})(scope, receive, send)
        public = path in {LOGIN_PATH, "/health", "/api/desktop/profile"} or path.startswith("/desktop-static/")
        if profile not in {"demo", "user"} and not public:
            return await RedirectResponse(LOGIN_PATH, status_code=307)(scope, receive, send)
        if profile == "demo":
            _ensure_demo_once()
        token = set_desktop_profile(profile if profile in {"demo", "user"} else "user")
        try:
            return await self.app(scope, receive, send)
        finally:
            reset_desktop_profile(token)


def _profile_switch_script() -> str:
    return """
document.addEventListener('DOMContentLoaded',async()=>{
  const context=await fetch('/api/desktop/profile').then(r=>r.json()).catch(()=>null);
  if(!context||document.querySelector('.desktop-profile-switch'))return;
  const link=document.createElement('a');link.className='desktop-profile-switch';
  link.href='/desktop-login';link.textContent=`${context.profile==='demo'?'Demo':'Il mio profilo'} · cambia`;
  const style=document.createElement('style');style.textContent='.desktop-profile-switch{position:fixed;right:18px;bottom:18px;z-index:9999;padding:11px 15px;border:1px solid #52605a;border-radius:999px;background:#202923ef;color:#f4f7f5!important;text-decoration:none!important;font:800 13px/1 system-ui,sans-serif;box-shadow:0 8px 28px #0008}.desktop-profile-switch:hover{border-color:#a7f432}';
  document.head.append(style);document.body.append(link);
});
"""


def _desktop_ui_script() -> str:
    """Keep the shared UI helpers without creating a HomeHub shortcut."""
    return """
document.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('dialog').forEach(dialog=>{dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close()})});
  document.querySelectorAll('.error,.message,.form-message').forEach(element=>{element.setAttribute('role','status');element.setAttribute('aria-live','polite')});
  if(!document.querySelector('meta[name="theme-color"]')){const meta=document.createElement('meta');meta.name='theme-color';meta.content=getComputedStyle(document.body).backgroundColor||'#07100d';document.head.append(meta)}
});
"""


def attach_desktop(app: FastAPI) -> None:
    static_dir = Path(__file__).parent / "static"
    ensure_theme_file(_data_dir())

    @app.get(LOGIN_PATH, include_in_schema=False)
    def desktop_login() -> FileResponse:
        return FileResponse(static_dir / "login.html")

    @app.post("/api/desktop/profile", include_in_schema=False)
    def select_profile(profile: str = Form(...)) -> RedirectResponse:
        selected = "demo" if profile == "demo" else "user"
        if selected == "demo" and _onboarding_complete():
            raise HTTPException(status_code=409, detail="La demo non è più disponibile dopo l’attivazione del profilo personale")
        if selected == "demo":
            _ensure_demo_once()
        else:
            _complete_onboarding()
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(PROFILE_COOKIE, selected, httponly=True, samesite="strict", max_age=31_536_000)
        return response

    @app.get("/api/desktop/profile", include_in_schema=False)
    def profile_context_with_request(request: Request) -> dict:
        if _onboarding_complete():
            return {"desktop": True, "profile": "user", "onboarding_complete": True}
        value = request.cookies.get(PROFILE_COOKIE, "user")
        return {"desktop": True, "profile": value if value in {"demo", "user"} else "user", "onboarding_complete": False}

    @app.get("/api/desktop/community", include_in_schema=False)
    def community_feed() -> dict:
        config = community_settings(_data_dir())
        if not config["enabled"]:
            return {"enabled": False, "name": config["name"], "events": [], "preferences": {}}
        feed, cached = fetch_feed(_data_dir(), config["feed_url"])
        return {**feed, "enabled": True, "cached": cached, "preferences": read_preferences(get_settings().data_dir)}

    @app.patch("/api/desktop/community/preference", include_in_schema=False)
    def community_preference(payload: CommunityPreference) -> dict:
        if not community_settings(_data_dir())["enabled"]:
            raise HTTPException(status_code=404, detail="Community non attiva")
        try:
            preferences = save_preference(get_settings().data_dir, payload.event_id, payload.state)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"event_id": payload.event_id, "state": preferences.get(payload.event_id, "none")}

    app.add_middleware(DesktopProfileMiddleware)
