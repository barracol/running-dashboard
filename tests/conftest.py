import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNNING_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RUNNING_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("RUNNING_UPLOAD_DIR", str(tmp_path / "uploads"))
    from app.main import app
    with TestClient(app) as test_client:
        yield test_client
