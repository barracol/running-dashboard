def sample():
    return {"activity_date":"2026-08-01","distance_m":10000,"duration_s":3300,"calories":650,"avg_heart_rate":152,"activity_type":"running","notes":"Lungo"}


def test_health_and_empty_summary(client):
    assert client.get("/health").json() == {"status":"ok"}
    assert client.get("/api/stats/summary").json()["activities"] == 0


def test_activity_crud_and_stats(client):
    created = client.post("/api/activities", json=sample())
    assert created.status_code == 201
    activity_id = created.json()["id"]
    assert client.get(f"/api/activities/{activity_id}").json()["distance_m"] == 10000
    updated = client.patch(f"/api/activities/{activity_id}", json={"notes":"Progressivo"})
    assert updated.json()["notes"] == "Progressivo"
    assert client.get("/api/stats/summary").json()["distance_m"] == 10000
    assert len(client.get("/api/stats/chart?period=month").json()) == 1
    assert client.delete(f"/api/activities/{activity_id}").status_code == 204
    assert client.get(f"/api/activities/{activity_id}").status_code == 404


def test_validation(client):
    payload = sample() | {"duration_s":0, "avg_heart_rate":999}
    assert client.post("/api/activities", json=payload).status_code == 422
    created = client.post("/api/activities", json=sample()).json()
    assert client.patch(f"/api/activities/{created['id']}", json={"distance_m":None}).status_code == 422


def test_file_staging_and_duplicate_detection(client):
    params={"activity_date":"2026-08-01","distance_m":5000,"duration_s":1600}
    files={"file":("run.gpx",b"<gpx></gpx>","application/gpx+xml")}
    first=client.post("/api/import",params=params,files=files)
    assert first.status_code == 201
    assert first.json()["status"] == "stored_not_parsed"
    assert client.post("/api/import",params=params,files=files).status_code == 409


def test_multisport_filters_yearly_chart_and_personal_bests(client):
    run = client.post("/api/activities", json=sample()).json()
    ride = client.post("/api/activities", json=sample() | {
        "activity_type":"cycling", "distance_m":45000, "duration_s":5400,
    }).json()
    swim = client.post("/api/activities", json=sample() | {
        "activity_type":"swimming", "distance_m":1500, "duration_s":2100,
    }).json()
    assert run["activity_type"] == "running"
    assert ride["activity_type"] == "cycling"
    assert swim["activity_type"] == "swimming"
    assert client.get("/api/stats/summary?sport=cycling").json()["distance_m"] == 45000
    running_chart = client.get("/api/stats/chart?period=year&sport=running").json()[0]
    cycling_chart = client.get("/api/stats/chart?period=year&sport=cycling").json()[0]
    assert running_chart["distance_km"] == 10
    assert cycling_chart["distance_km"] == 45
    assert cycling_chart["avg_speed_kmh"] == 30
    assert len(client.get("/api/activities?sport=swimming").json()) == 1
    assert len(client.get("/api/stats/chart?period=year").json()) == 1
    sports = {item["activity_type"] for item in client.get("/api/stats/sports").json()}
    assert sports == {"running", "cycling", "swimming"}
    bests = client.get("/api/stats/personal-bests").json()
    assert bests[0]["label"] == "10 km"
    assert bests[0]["activity"]["id"] == run["id"]
    assert bests[1]["activity"] is None


def test_drafts_are_separate_from_verified_stats_and_planning_crud(client):
    draft = client.post("/api/drafts", json=sample() | {"notes":"Sensazioni libere"})
    assert draft.status_code == 201
    assert draft.json()["record_status"] == "draft"
    assert client.get("/api/stats/summary").json()["activities"] == 0
    assert client.get("/api/drafts").json()[0]["id"] == draft.json()["id"]
    assert len(client.get("/api/drafts/trend").json()) == 1
    assert client.patch(f"/api/drafts/{draft.json()['id']}", json={"notes":"Aggiornato"}).status_code == 200

    exported = client.get("/api/drafts/export.csv")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in exported.headers["content-disposition"]
    assert "activity_date;activity_type;distance_km" in exported.text
    assert "2026-08-01;running;10.000;3300;00:55:00;330;5:30/km;10.909" in exported.text
    assert "Aggiornato" in exported.text

    planned = client.post("/api/planned-workouts", json={
        "planned_date":"2026-08-03", "activity_type":"running", "title":"Lungo facile",
        "target_distance_m":18000, "target_duration_s":7200, "notes":"Zona 2",
    })
    assert planned.status_code == 201
    planned_id = planned.json()["id"]
    week = client.get("/api/planned-workouts?start=2026-08-03&end=2026-08-09").json()
    assert week[0]["title"] == "Lungo facile"
    assert client.patch(f"/api/planned-workouts/{planned_id}", json={"status":"completed"}).json()["status"] == "completed"
    assert client.delete(f"/api/planned-workouts/{planned_id}").status_code == 204
    cycling_draft = client.post("/api/drafts", json=sample() | {
        "activity_date": "2026-08-02", "activity_type": "cycling",
        "distance_m": 40000, "duration_s": 5400,
    })
    assert cycling_draft.status_code == 201
    running_trend = client.get("/api/drafts/trend?sport=running").json()
    assert all(item["distance_km"] < 40 for item in running_trend)
    assert client.delete(f"/api/drafts/{cycling_draft.json()['id']}").status_code == 204
    assert client.delete(f"/api/drafts/{draft.json()['id']}").status_code == 204


def test_ai_coach_preview_requires_key_and_accepts_confirmed_plan(client, monkeypatch):
    from app import ai_coach
    from app.schemas import CoachPlan

    request = {
        "week_start": "2026-08-10", "sessions": 2,
        "available_days": ["tuesday", "sunday"],
        "goal": "Preparare una 10 km", "instructions": "Lungo domenica",
    }
    assert client.get("/api/coach/status").json()["configured"] is False
    assert client.post("/api/coach/plan", json=request).status_code == 503

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    expected = CoachPlan.model_validate({
        "week_start": "2026-08-10",
        "analysis_summary": "Carico recente regolare.",
        "load_guidance": "Aumento prudente.",
        "cautions": [],
        "workouts": [
            {"planned_date": "2026-08-11", "activity_type": "running", "title": "Corsa facile",
             "target_distance_m": 6000, "target_duration_s": 2400, "intensity": "easy",
             "notes": "Ritmo conversazionale", "rationale": "Recupero attivo"},
            {"planned_date": "2026-08-16", "activity_type": "running", "title": "Lungo",
             "target_distance_m": 12000, "target_duration_s": 4800, "intensity": "long",
             "notes": "Regolare", "rationale": "Costruzione aerobica"},
        ],
    })
    seen = {}

    def fake_generate(payload, context):
        seen["context"] = context
        return expected

    monkeypatch.setattr(ai_coach, "generate_plan", fake_generate)
    generated = client.post("/api/coach/plan", json=request)
    assert generated.status_code == 200
    assert generated.json()["workouts"][1]["title"] == "Lungo"
    assert "weekly_totals" in seen["context"]

    accepted = client.post("/api/coach/accept", json=generated.json())
    assert accepted.status_code == 201
    assert len(accepted.json()["created"]) == 2
    week = client.get("/api/planned-workouts?start=2026-08-10&end=2026-08-16").json()
    assert "Coach AI" in week[0]["notes"]
    assert client.post("/api/coach/accept", json=generated.json()).status_code == 409


def test_ai_coach_rejects_more_swims_than_total_sessions(client):
    response = client.post("/api/coach/plan", json={
        "week_start": "2026-08-10", "sessions": 2, "swimming_sessions": 3,
        "available_days": [], "goal": "Continuità", "instructions": "",
    })
    assert response.status_code == 422


def test_ai_coach_rejects_more_dedicated_sports_than_total_sessions(client):
    response = client.post("/api/coach/plan", json={
        "week_start": "2026-08-10", "sessions": 3,
        "swimming_sessions": 2, "cycling_sessions": 2,
        "available_days": [], "goal": "Continuità", "instructions": "",
    })
    assert response.status_code == 422


def test_ai_coach_accepts_open_feedback_question(client, monkeypatch):
    from app import ai_coach
    from app.schemas import CoachFeedback

    monkeypatch.setattr(ai_coach, "configured", lambda: True)
    monkeypatch.setattr(
        ai_coach,
        "generate_feedback",
        lambda request, context: CoachFeedback(
            answer=f"Risposta a: {request.question}",
            highlights=["Tre allenamenti recenti"],
            cautions=[],
        ),
    )
    response = client.post("/api/coach/feedback", json={"question": "Come sto andando?"})
    assert response.status_code == 200
    assert response.json()["highlights"] == ["Tre allenamenti recenti"]


def test_race_planning_crud_and_registration(client):
    race = client.post("/api/planned-races", json={
        "race_date":"2026-11-08", "name":"Mezza del mare", "location":"Trapani",
        "distance_m":21097, "cost_cents":3500, "website_url":"https://example.com/race",
        "notes":"Percorso veloce", "registered":False,
    })
    assert race.status_code == 201
    race_id = race.json()["id"]
    assert race.json()["registered"] is False
    annual = client.get("/api/planned-races?start=2026-01-01&end=2026-12-31").json()
    assert annual[0]["cost_cents"] == 3500
    confirmed = client.patch(f"/api/planned-races/{race_id}", json={"registered":True})
    assert confirmed.json()["registered"] is True
    assert client.get("/api/planned-races?start=2026-12-31&end=2026-01-01").status_code == 422
    assert client.delete(f"/api/planned-races/{race_id}").status_code == 204


def test_smart_scale_entries_crud(client):
    entry = client.post("/api/scale-entries", json={
        "measured_date":"2026-08-05", "weight_kg":72.45, "body_fat_percent":14.2,
        "muscle_mass_kg":58.1, "water_percent":61.0, "bmi":22.4,
        "visceral_fat":6, "notes":"Mattina",
    })
    assert entry.status_code == 201
    entry_id = entry.json()["id"]
    assert client.get("/api/scale-entries").json()[0]["weight_kg"] == 72.45
    assert client.patch(f"/api/scale-entries/{entry_id}", json={"weight_kg":72.1}).json()["weight_kg"] == 72.1
    assert client.post("/api/scale-entries", json={"measured_date":"2026-08-05"}).status_code == 422
    assert client.delete(f"/api/scale-entries/{entry_id}").status_code == 204


def test_sports_documents_singleton(client):
    initial = client.get("/api/sports-documents")
    assert initial.status_code == 200
    assert initial.json()["run_card_number"] == ""
    updated = client.put("/api/sports-documents", json={
        "run_card_number": "RC-123456",
        "run_card_expiry": "2026-12-31",
        "medical_certificate_expiry": "2027-02-15",
    })
    assert updated.status_code == 200
    assert updated.json()["run_card_number"] == "RC-123456"
    assert client.get("/api/sports-documents").json()["medical_certificate_expiry"] == "2027-02-15"
    expired = client.put("/api/sports-documents", json={
        "run_card_number": "RC-123456",
        "run_card_expiry": "2025-12-31",
        "medical_certificate_expiry": "2025-06-15",
    })
    assert expired.status_code == 200
    assert expired.json()["medical_certificate_expiry"] == "2025-06-15"
    assert client.put("/api/sports-documents", json={"run_card_number": "", "run_card_expiry": "bad"}).status_code == 422


def test_running_shoes_track_activity_distance_and_photo(client):
    shoe=client.post("/api/shoes",json={"name":"Daily Trainer","brand":"Asics","model":"Nimbus","max_distance_m":700000,"active":True})
    assert shoe.status_code==201;shoe_id=shoe.json()["id"]
    activity=client.post("/api/activities",json=sample()|{"shoe_id":shoe_id})
    draft=client.post("/api/drafts",json=sample()|{"distance_m":5000,"shoe_id":shoe_id})
    assert activity.status_code==draft.status_code==201
    summary=client.get("/api/shoes").json()[0]
    assert summary["distance_m"]==15000
    assert summary["remaining_m"]==685000
    assert summary["activities"]==2
    assert summary["usage_percent"]==2.1
    assert summary["tracked_distance_m"]==15000
    assert summary["avg_speed_kmh"]==round(15000*3.6/6600,2)
    adjusted=client.patch(f"/api/shoes/{shoe_id}",json={"manual_distance_m":120000})
    assert adjusted.status_code==200
    assert adjusted.json()["distance_m"]==135000
    assert adjusted.json()["remaining_m"]==565000
    assert client.delete(f"/api/drafts/{draft.json()['id']}").status_code==204
    summary=client.get("/api/shoes").json()[0]
    assert summary["tracked_distance_m"]==10000
    assert summary["distance_m"]==130000
    photo=client.post(f"/api/shoes/{shoe_id}/photo",files={"file":("shoe.jpg",b"\xff\xd8\xfftest","image/jpeg")})
    assert photo.status_code==200
    assert photo.json()["photo_url"]==f"/api/shoes/{shoe_id}/photo"
    assert client.get(photo.json()["photo_url"]).status_code==200
    assert client.patch(f"/api/activities/{activity.json()['id']}",json={"distance_m":12000}).status_code==200
    assert client.get("/api/shoes").json()[0]["distance_m"]==132000
    assert client.delete(f"/api/shoes/{shoe_id}").status_code==204
    assert client.get(f"/api/activities/{activity.json()['id']}").json()["shoe_id"] is None
