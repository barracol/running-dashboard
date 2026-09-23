from datetime import date


def activity():
    return {"id":"i123","name":"Morning Run","type":"Run","start_date_local":"2026-09-20T08:00:00","distance":10000.2,"moving_time":3000,"elapsed_time":3050,"calories":700,"average_heartrate":151,"source":"GARMIN_CONNECT"}


def test_intervals_status_disabled(client, monkeypatch):
    monkeypatch.delenv("INTERVALS_ATHLETE_ID", raising=False); monkeypatch.delenv("INTERVALS_API_KEY", raising=False)
    assert client.get("/api/intervals/status").json()["configured"] is False


def test_preview_and_idempotent_import(client, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "intervals_activities", lambda start, end: [__import__("app.intervals_client", fromlist=["normalize_activity"]).normalize_activity(activity())])
    params={"start_date":"2026-09-01","end_date":"2026-09-30"}
    preview=client.get("/api/intervals/preview",params=params).json(); assert preview["new"]==1
    first=client.post("/api/intervals/import",params=params); assert first.status_code==201; assert first.json()["imported"]==1
    second=client.post("/api/intervals/import",params=params).json(); assert second["imported"]==0; assert second["duplicates"]==1
    saved=client.get("/api/activities").json()[0]; assert saved["source"]=="intervals.icu"; assert saved["distance_m"]==10000


def test_planning_draft_does_not_block_official_import(client, monkeypatch):
    from app import main
    normalized = __import__("app.intervals_client", fromlist=["normalize_activity"]).normalize_activity(activity())
    monkeypatch.setattr(main, "intervals_activities", lambda start, end: [normalized])
    draft = {"activity_date":"2026-09-20","distance_m":10000,"duration_s":3000,"activity_type":"running","notes":"Pianificato"}
    assert client.post("/api/drafts", json=draft).status_code == 201
    params={"start_date":"2026-09-01","end_date":"2026-09-30"}
    preview=client.get("/api/intervals/preview",params=params).json()
    assert preview["new"] == 1 and preview["duplicates"] == 0
    imported=client.post("/api/intervals/import",params=params).json()
    assert imported["imported"] == 1
    assert len(client.get("/api/drafts").json()) == 1
