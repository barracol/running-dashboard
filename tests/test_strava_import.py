import csv
import gzip
from datetime import date

from app.strava_import import import_export


def test_strava_import_is_localized_multisport_and_idempotent(client, tmp_path):
    export = tmp_path / "export_test"
    activities = export / "activities"
    activities.mkdir(parents=True)
    source = activities / "123.gpx.gz"
    with gzip.open(source, "wb") as stream:
        stream.write(b"<gpx><trk><type>strolling</type></trk></gpx>")
    fields = [
        "ID attività", "Data dell’attività", "Nome attività", "Tipo attività",
        "Tempo trascorso", "Tempo in movimento", "Distanza", "Frequenza cardiaca media",
        "Calorie", "Nome del file", "Descrizione dell’attività", "Nota privata sulle attività",
    ]
    with (export / "activities.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "ID attività":"123", "Data dell’attività":"2 ago 2026, 17:43:26",
            "Nome attività":"Passeggiata serale", "Tipo attività":"Allenamento generico", "Tempo trascorso":"1900.0",
            "Tempo in movimento":"1800.0", "Distanza":"1500.4", "Frequenza cardiaca media":"135.2",
            "Calorie":"350.0", "Frequenza cardiaca media":"0.0",
            "Nome del file":"activities/123.gpx.gz",
        })
    first = import_export(export)
    assert first.imported == 1
    activity = client.get("/api/activities").json()[0]
    assert activity["activity_type"] == "walking"
    assert activity["distance_m"] == 1500
    assert activity["duration_s"] == 1800
    assert activity["avg_heart_rate"] is None
    assert activity["activity_name"] == "Passeggiata serale"
    detail = client.get(f"/api/activities/{activity['id']}/detail")
    assert detail.status_code == 200
    assert detail.json()["track"]["status"] == "no_track"
    original = client.get(f"/api/activities/{activity['id']}/original")
    assert original.status_code == 200
    assert original.content
    second = import_export(export)
    assert second.imported == 0
    assert second.duplicate == 1


def test_strava_import_respects_inclusive_start_date(client, tmp_path):
    export = tmp_path / "export_cutoff"
    export.mkdir()
    fields = [
        "Activity ID", "Activity Date", "Activity Name", "Activity Type",
        "Elapsed Time", "Moving Time", "Distance", "Filename",
    ]
    with (export / "activities.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"Activity ID":"old", "Activity Date":"Aug 06, 2026, 08:00:00 AM", "Activity Name":"Old", "Activity Type":"Run", "Elapsed Time":"600", "Moving Time":"600", "Distance":"1000"})
        writer.writerow({"Activity ID":"new", "Activity Date":"Aug 07, 2026, 08:00:00 AM", "Activity Name":"New", "Activity Type":"Run", "Elapsed Time":"1200", "Moving Time":"1200", "Distance":"2000"})
    report = import_export(export, start_date=date(2026, 8, 7))
    assert report.imported == 1
    assert report.skipped_before_date == 1
    activities = client.get("/api/activities").json()
    assert [activity["activity_name"] for activity in activities] == ["New"]
