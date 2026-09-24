import hashlib
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from desktop.integration import attach_desktop


def desktop_test_app(tmp_path, monkeypatch) -> FastAPI:
    monkeypatch.setenv("RUNNING_DESKTOP", "1")
    monkeypatch.setenv("RUNNING_DATA_DIR", str(tmp_path))
    app = FastAPI()

    @app.get("/")
    def home():
        return {"database": str(get_settings().database_path)}

    attach_desktop(app)
    return app


def test_desktop_requires_profile_selection(tmp_path, monkeypatch):
    client = TestClient(desktop_test_app(tmp_path, monkeypatch))
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/desktop-login"


def test_demo_and_user_profiles_are_isolated(tmp_path, monkeypatch):
    client = TestClient(desktop_test_app(tmp_path, monkeypatch))

    response = client.post("/api/desktop/profile", data={"profile": "demo"}, follow_redirects=False)
    assert response.status_code == 303
    assert client.get("/api/desktop/profile").json()["profile"] == "demo"
    demo_path = client.get("/").json()["database"]
    assert "/profiles/demo/" in demo_path
    assert (tmp_path / "profiles" / "demo" / "running.db").exists()

    client.post("/api/desktop/profile", data={"profile": "user"}, follow_redirects=False)
    assert client.get("/api/desktop/profile").json()["profile"] == "user"
    user_path = client.get("/").json()["database"]
    assert "/profiles/user/" in user_path
    assert user_path != demo_path


def test_homehub_script_is_replaced_by_profile_switch(tmp_path, monkeypatch):
    client = TestClient(desktop_test_app(tmp_path, monkeypatch))
    script = client.get("/static/hub-link.js").text
    assert "desktop-profile-switch" in script
    assert "Home Hub" not in script


def test_desktop_ui_script_does_not_create_homehub_link(tmp_path, monkeypatch):
    client = TestClient(desktop_test_app(tmp_path, monkeypatch))
    client.post("/api/desktop/profile", data={"profile": "user"})
    script = client.get("/static/ui-standard.js").text
    assert "Home Hub" not in script
    assert "ui-home-hub" not in script
    assert "querySelectorAll('dialog')" in script


def test_user_profile_completes_onboarding_and_hides_demo(tmp_path, monkeypatch):
    client = TestClient(desktop_test_app(tmp_path, monkeypatch))
    response = client.post("/api/desktop/profile", data={"profile":"user"}, follow_redirects=False)
    assert response.status_code == 303
    assert client.get("/api/desktop/profile").json()["onboarding_complete"] is True
    assert client.get("/desktop-login", follow_redirects=False).headers["location"] == "/"
    assert client.get("/static/hub-link.js").text == ""
    rejected = client.post("/api/desktop/profile", data={"profile":"demo"})
    assert rejected.status_code == 409


def test_desktop_settings_save_keys_without_returning_them(tmp_path, monkeypatch):
    client = TestClient(desktop_test_app(tmp_path, monkeypatch))
    client.post("/api/desktop/profile", data={"profile":"user"})
    response = client.put("/api/desktop/settings", json={
        "intervals_athlete_id":"0", "intervals_api_key":"intervals-secret",
        "openai_api_key":"openai-secret", "openai_model":"test-model",
    })
    assert response.status_code == 200
    assert response.json() == {
        "intervals_athlete_id":"0", "intervals_configured":True,
        "openai_configured":True, "openai_model":"test-model", "community_active":False,
    }
    saved = (tmp_path / "desktop-settings.json").read_text()
    assert "intervals-secret" in saved and "openai-secret" in saved
    assert "intervals-secret" not in response.text and "openai-secret" not in response.text
    assert __import__("os").environ["INTERVALS_API_KEY"] == "intervals-secret"


def test_desktop_settings_can_verify_intervals(tmp_path, monkeypatch):
    from desktop import integration
    client = TestClient(desktop_test_app(tmp_path, monkeypatch))
    client.post("/api/desktop/profile", data={"profile":"user"})
    client.put("/api/desktop/settings", json={"intervals_athlete_id":"0", "intervals_api_key":"secret"})
    monkeypatch.setattr(integration, "list_intervals_activities", lambda oldest, newest: [{"id":"i1"}])
    assert client.post("/api/desktop/settings/test-intervals").json() == {"connected":True,"activities_today":1}


def test_community_code_unlocks_theme_without_being_saved(tmp_path, monkeypatch):
    from desktop import theme
    profile = next(item for item in theme.COMMUNITY_PROFILES.values() if item["preset"] == "community-violet")
    monkeypatch.setattr(theme, "COMMUNITY_PROFILES", {hashlib.sha256(b"test-code").hexdigest(): profile})
    client = TestClient(desktop_test_app(tmp_path, monkeypatch))
    client.post("/api/desktop/profile", data={"profile":"user"})
    rejected = client.put("/api/desktop/settings", json={"community_code":"wrong"})
    assert rejected.status_code == 422
    response = client.put("/api/desktop/settings", json={"community_code":"test-code"})
    assert response.status_code == 200
    assert response.json()["community_active"] is True
    assert "test-code" not in (tmp_path / "desktop-settings.json").read_text()
    assert json.loads((tmp_path / "theme.json").read_text())["preset"] == "community-violet"


def test_second_community_code_uses_its_own_profile(tmp_path, monkeypatch):
    from desktop import theme
    profile = next(item for item in theme.COMMUNITY_PROFILES.values() if item["preset"] == "borgorun")
    monkeypatch.setattr(theme, "COMMUNITY_PROFILES", {hashlib.sha256(b"another-test-code").hexdigest(): profile})
    client = TestClient(desktop_test_app(tmp_path, monkeypatch))
    client.post("/api/desktop/profile", data={"profile":"user"})
    response = client.put("/api/desktop/settings", json={"community_code":"another-test-code"})
    assert response.status_code == 200
    theme = json.loads((tmp_path / "theme.json").read_text())
    assert theme["preset"] == "borgorun"
    assert theme["community"]["id"] == "borgolavezzaro-runner"
