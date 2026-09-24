from pathlib import Path

from desktop.launcher import configure_environment, load_desktop_settings, user_data_dir


def test_configure_environment_uses_local_data_and_optional_ai_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("RUNNING_OPENAI_MODEL", raising=False)
    monkeypatch.delenv("INTERVALS_ATHLETE_ID", raising=False)
    monkeypatch.delenv("INTERVALS_API_KEY", raising=False)
    (tmp_path / "desktop-settings.json").write_text(
        '{"openai_api_key":"test-key","openai_model":"test-model","intervals_athlete_id":"0","intervals_api_key":"intervals-key"}', encoding="utf-8"
    )

    configure_environment(tmp_path)

    assert Path(__import__("os").environ["RUNNING_DATA_DIR"]) == tmp_path
    assert __import__("os").environ["OPENAI_API_KEY"] == "test-key"
    assert __import__("os").environ["RUNNING_OPENAI_MODEL"] == "test-model"
    assert __import__("os").environ["INTERVALS_ATHLETE_ID"] == "0"
    assert __import__("os").environ["INTERVALS_API_KEY"] == "intervals-key"


def test_invalid_desktop_settings_are_ignored(tmp_path):
    (tmp_path / "desktop-settings.json").write_text("not json", encoding="utf-8")
    assert load_desktop_settings(tmp_path) == {}


def test_user_data_dir_can_be_overridden_for_portable_tests(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNNING_DESKTOP_DATA_DIR", str(tmp_path))
    assert user_data_dir() == tmp_path.resolve()
