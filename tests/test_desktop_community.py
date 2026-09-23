import json

from desktop.community import _validate_feed, read_preferences, save_preference
from desktop.theme import community_settings


def test_synopsys_preset_enables_community(tmp_path):
    (tmp_path / "theme.json").write_text(json.dumps({"preset": "synopsys", "colors": {}}))
    assert community_settings(tmp_path)["enabled"] is True


def test_feed_validation_and_url_filtering():
    result = _validate_feed({"events": [
        {"id": "run-1", "type": "workout", "title": "Lungo", "date": "2026-10-03", "website": "https://example.com"},
        {"id": "run-2", "type": "race", "title": "Gara", "date": "2026-10-04", "website": "javascript:alert(1)"},
        {"id": "bad", "type": "other", "title": "No", "date": "2026-10-05"},
    ]})
    assert len(result["events"]) == 2
    assert result["events"][0]["website"] == "https://example.com"
    assert "website" not in result["events"][1]


def test_preferences_are_local(tmp_path):
    save_preference(tmp_path, "run-1", "attending")
    assert read_preferences(tmp_path) == {"run-1": "attending"}
    save_preference(tmp_path, "run-1", "none")
    assert read_preferences(tmp_path) == {}
