import json
from datetime import datetime, timezone

from desktop import updates


def test_newer_release_is_reported_and_cached(tmp_path, monkeypatch):
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, _limit):
            return json.dumps({
                "tag_name": "v0.3.0",
                "html_url": "https://github.com/barracol/running-dashboard/releases/tag/v0.3.0",
            }).encode()

    monkeypatch.setattr(updates, "urlopen", lambda *args, **kwargs: Response())
    result = updates.check_for_update(tmp_path)
    assert result["available"] is True
    assert result["current_version"] == "0.2.0"
    assert "0.3.0" in result["release_url"]
    assert (tmp_path / updates.CACHE_FILENAME).exists()


def test_current_or_older_release_does_not_notify(tmp_path):
    (tmp_path / updates.CACHE_FILENAME).write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "latest_version": "v0.1.7",
        "release_url": "https://github.com/barracol/running-dashboard/releases/tag/v0.1.7",
    }))
    result = updates.check_for_update(tmp_path)
    assert result["available"] is False
    assert result["latest_version"] == "0.1.7"
