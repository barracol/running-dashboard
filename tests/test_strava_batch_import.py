import csv
import io
import zipfile


def strava_zip() -> bytes:
    csv_stream = io.StringIO(newline="")
    fields = ["Activity ID", "Activity Date", "Activity Name", "Activity Type", "Elapsed Time", "Moving Time", "Distance", "Filename"]
    writer = csv.DictWriter(csv_stream, fieldnames=fields)
    writer.writeheader()
    writer.writerow({"Activity ID":"old", "Activity Date":"Aug 06, 2026, 08:00:00 AM", "Activity Name":"Old", "Activity Type":"Run", "Elapsed Time":"600", "Moving Time":"600", "Distance":"1000"})
    writer.writerow({"Activity ID":"new", "Activity Date":"Aug 07, 2026, 08:00:00 AM", "Activity Name":"New", "Activity Type":"Run", "Elapsed Time":"1200", "Moving Time":"1200", "Distance":"2000"})
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("strava-export/activities.csv", csv_stream.getvalue())
    return output.getvalue()


def test_batch_zip_import_applies_cutoff_and_is_idempotent(client):
    files = [("files", ("export.zip", strava_zip(), "application/zip"))]
    first = client.post("/api/import/strava-batch?start_date=2026-08-07", files=files)
    assert first.status_code == 201
    assert first.json()["totals"]["imported"] == 1
    assert first.json()["totals"]["skipped_before_date"] == 1
    second = client.post("/api/import/strava-batch?start_date=2026-08-07", files=files)
    assert second.status_code == 201
    assert second.json()["totals"]["duplicate"] == 1


def test_batch_zip_rejects_path_traversal(client):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("../activities.csv", "Activity ID\n1\n")
    response = client.post(
        "/api/import/strava-batch?start_date=2026-08-07",
        files=[("files", ("unsafe.zip", output.getvalue(), "application/zip"))],
    )
    assert response.status_code == 400
