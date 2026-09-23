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


def test_user_profile_completes_onboarding_and_hides_demo(tmp_path, monkeypatch):
    client = TestClient(desktop_test_app(tmp_path, monkeypatch))
    response = client.post("/api/desktop/profile", data={"profile":"user"}, follow_redirects=False)
    assert response.status_code == 303
    assert client.get("/api/desktop/profile").json()["onboarding_complete"] is True
    assert client.get("/desktop-login", follow_redirects=False).headers["location"] == "/"
    assert client.get("/static/hub-link.js").text == ""
    rejected = client.post("/api/desktop/profile", data={"profile":"demo"})
    assert rejected.status_code == 409
