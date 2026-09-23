"""Desktop-only profile selector, editable theme and HomeHub-link replacement."""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.datastructures import Headers

from app.config import reset_desktop_profile, set_desktop_profile
from .demo_data import ensure_demo_data
from .theme import ensure_theme_file, theme_css


PROFILE_COOKIE = "running_desktop_profile"
LOGIN_PATH = "/desktop-login"
_demo_lock = Lock()
_demo_ready = False

def _data_dir() -> Path:
    return Path(os.environ.get("RUNNING_DATA_DIR", Path.home() / ".running-dashboard"))


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
        headers = Headers(scope=scope)
        profile = headers.get("cookie", "")
        profile = next((part.split("=", 1)[1] for part in profile.split("; ") if part.startswith(f"{PROFILE_COOKIE}=")), "")

        if path == "/static/hub-link.js":
            return await Response(_profile_switch_script(), media_type="application/javascript")(scope, receive, send)
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


def attach_desktop(app: FastAPI) -> None:
    static_dir = Path(__file__).parent / "static"
    ensure_theme_file(_data_dir())

    @app.get(LOGIN_PATH, include_in_schema=False)
    def desktop_login() -> FileResponse:
        return FileResponse(static_dir / "login.html")

    @app.post("/api/desktop/profile", include_in_schema=False)
    def select_profile(profile: str = Form(...)) -> RedirectResponse:
        selected = "demo" if profile == "demo" else "user"
        if selected == "demo":
            _ensure_demo_once()
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(PROFILE_COOKIE, selected, httponly=True, samesite="strict", max_age=31_536_000)
        return response

    @app.get("/api/desktop/profile", include_in_schema=False)
    def profile_context_with_request(request: Request) -> dict:
        value = request.cookies.get(PROFILE_COOKIE, "user")
        return {"desktop": True, "profile": value if value in {"demo", "user"} else "user"}

    app.add_middleware(DesktopProfileMiddleware)
