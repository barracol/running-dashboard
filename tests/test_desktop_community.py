import hashlib
import json

from desktop import theme
from desktop.community import _validate_feed, read_preferences, save_preference
from desktop.theme import activate_community_theme, community_settings, load_theme


def test_violet_preset_enables_community(tmp_path):
    (tmp_path / "theme.json").write_text(json.dumps({"preset": "community-violet", "colors": {}}))
    assert community_settings(tmp_path)["enabled"] is True


def test_borgolavezzaro_code_selects_nature_theme_and_feed(tmp_path, monkeypatch):
    profile = next(item for item in theme.COMMUNITY_PROFILES.values() if item["preset"] == "borgorun")
    monkeypatch.setattr(theme, "COMMUNITY_PROFILES", {hashlib.sha256(b"test-code").hexdigest(): profile})
    assert activate_community_theme(tmp_path, "test-code") is True
    preset, colors = load_theme(tmp_path)
    config = community_settings(tmp_path)
    assert preset == "borgorun"
    assert colors["primary"] == "#9bd44e"
    assert config["name"] == "BorgolavezzaroRunner"
    assert config["id"] == "borgolavezzaro-runner"
    assert config["feed_url"].endswith("/data/borgolavezzaro-runner.json")


def test_feed_validation_and_url_filtering():
    result = _validate_feed({"events": [
        {"id": "run-1", "type": "workout", "title": "Lungo", "date": "2026-10-03", "duration": "1:20:00", "website": "https://example.com"},
        {"id": "run-2", "type": "race", "title": "Gara", "date": "2026-10-04", "website": "javascript:alert(1)"},
        {"id": "bad", "type": "other", "title": "No", "date": "2026-10-05"},
    ]})
    assert len(result["events"]) == 2
    assert result["events"][0]["website"] == "https://example.com"
    assert result["events"][0]["duration"] == "1:20:00"
    assert "website" not in result["events"][1]


def test_preferences_are_local(tmp_path):
    save_preference(tmp_path, "run-1", "attending")
    assert read_preferences(tmp_path) == {"run-1": "attending"}
    save_preference(tmp_path, "run-1", "none")
    assert read_preferences(tmp_path) == {}


def test_preferences_are_isolated_per_community(tmp_path):
    save_preference(tmp_path, "run-1", "attending", "borgolavezzaro-runner")
    assert read_preferences(tmp_path, "borgolavezzaro-runner") == {"run-1": "attending"}
    assert read_preferences(tmp_path, "running-community") == {}
