from contextlib import asynccontextmanager
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
import csv
import io
import os
import secrets
import tempfile
import zipfile

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import migrate
from . import repository
from . import ai_coach
from .schemas import (
    Activity, ActivityCreate, ActivityType, ActivityUpdate, ImportResult,
    PlannedWorkout, PlannedWorkoutCreate, PlannedWorkoutUpdate,
    PlannedRace, PlannedRaceCreate, PlannedRaceUpdate,
    ScaleEntry, ScaleEntryCreate, ScaleEntryUpdate,
    SportsDocuments, SportsDocumentsUpdate,
    RunningShoe, RunningShoeCreate, RunningShoeUpdate,
    CoachAcceptResult, CoachFeedback, CoachFeedbackRequest, CoachPlan, CoachPlanRequest,
)
from .tracks import activity_track
from .strava_import import import_export
from .intervals_client import (
    IntervalsError, configuration as intervals_configuration,
    download_activity_file as intervals_activity_file,
    list_activities as intervals_activities,
)

BASE_DIR = Path(__file__).parent
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_STRAVA_ZIP_BYTES = 1024 * 1024 * 1024
MAX_STRAVA_UNCOMPRESSED_BYTES = 5 * 1024 * 1024 * 1024
MAX_STRAVA_ZIP_ENTRIES = 50_000


def _safe_extract_zip(archive_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) > MAX_STRAVA_ZIP_ENTRIES:
            raise ValueError("L'archivio contiene troppi file")
        if sum(member.file_size for member in members) > MAX_STRAVA_UNCOMPRESSED_BYTES:
            raise ValueError("L'archivio decompresso supera 5 GB")
        root = destination.resolve()
        for member in members:
            target = (destination / member.filename).resolve()
            if target != root and root not in target.parents:
                raise ValueError("L'archivio contiene un percorso non sicuro")
            if member.flag_bits & 0x1:
                raise ValueError("Gli ZIP protetti da password non sono supportati")
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("L'archivio contiene collegamenti simbolici non supportati")
        archive.extractall(destination)


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate()
    yield


app = FastAPI(title="Running Dashboard", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/activity/{activity_id}", include_in_schema=False)
def activity_page(activity_id: int) -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "detail.html")


@app.get("/planning", include_in_schema=False)
def planning_page() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "planning.html")


@app.get("/races", include_in_schema=False)
def races_page() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "races.html")


@app.get("/exercises", include_in_schema=False)
def exercises_page() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "exercises.html")


@app.get("/exercises/running-strength", include_in_schema=False)
def running_strength_page() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "exercise-document.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/activities", response_model=list[Activity])
def activities(
    limit: int = Query(100, ge=1, le=2000), offset: int = Query(0, ge=0),
    sport: ActivityType | None = Query(None),
):
    return repository.list_activities(limit, offset, sport)


@app.get("/api/activities/{activity_id}", response_model=Activity)
def activity(activity_id: int):
    item = repository.get_activity(activity_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return item


@app.get("/api/activities/{activity_id}/detail")
def activity_detail(activity_id: int):
    item = repository.get_activity(activity_id)
    file_info = repository.get_activity_file(activity_id)
    if item is None or file_info is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    track = {"status": "missing", "format": None, "points": []}
    if file_info["original_file_path"]:
        path = (get_settings().upload_dir / file_info["original_file_path"]).resolve()
        upload_dir = get_settings().upload_dir.resolve()
        if upload_dir in path.parents and path.is_file():
            try:
                track = activity_track(path)
            except Exception:
                track = {"status": "invalid", "format": path.suffix, "points": []}
    return {"activity": item, "track": track, "has_original_file": bool(file_info["original_file_path"])}


@app.get("/api/activities/{activity_id}/original")
def activity_original(activity_id: int):
    file_info = repository.get_activity_file(activity_id)
    if file_info is None or not file_info["original_file_path"]:
        raise HTTPException(status_code=404, detail="Original file not found")
    upload_dir = get_settings().upload_dir.resolve()
    path = (upload_dir / file_info["original_file_path"]).resolve()
    if upload_dir not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Original file not found")
    return FileResponse(path, filename=file_info["original_filename"] or path.name)


@app.post("/api/activities", response_model=Activity, status_code=status.HTTP_201_CREATED)
def create_activity(payload: ActivityCreate):
    if payload.shoe_id and repository.get_shoe(payload.shoe_id) is None:
        raise HTTPException(status_code=404, detail="Running shoe not found")
    return repository.create_activity(payload)


@app.patch("/api/activities/{activity_id}", response_model=Activity)
def update_activity(activity_id: int, payload: ActivityUpdate):
    if payload.shoe_id and repository.get_shoe(payload.shoe_id) is None:
        raise HTTPException(status_code=404, detail="Running shoe not found")
    item = repository.update_activity(activity_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return item


@app.delete("/api/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(activity_id: int):
    if not repository.delete_activity(activity_id):
        raise HTTPException(status_code=404, detail="Activity not found")


@app.get("/api/stats/summary")
def stats_summary(sport: ActivityType | None = Query(None)):
    return repository.summary(sport)


@app.get("/api/stats/chart")
def stats_chart(
    period: str = Query("week", pattern="^(week|month|year)$"),
    sport: ActivityType | None = Query(None),
):
    return repository.chart_data(period, sport)


@app.get("/api/stats/sports")
def stats_sports():
    return repository.sports_summary()


@app.get("/api/stats/personal-bests")
def stats_personal_bests():
    return repository.running_personal_bests()


@app.get("/api/drafts", response_model=list[Activity])
def drafts(limit: int = Query(500, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return repository.list_activities(limit, offset, record_status="draft")


@app.get("/api/drafts/export.csv", response_class=Response)
def export_drafts_csv():
    output = io.StringIO()
    fieldnames = [
        "id", "activity_date", "activity_type", "distance_km", "duration_s",
        "duration", "pace_seconds_per_km", "pace", "avg_speed_kmh",
        "calories", "avg_heart_rate", "shoe", "notes",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=";", lineterminator="\n")
    writer.writeheader()
    for item in repository.list_drafts_for_export():
        distance_km = item["distance_m"] / 1000
        duration_s = item["duration_s"]
        pace_s = round(duration_s / distance_km) if distance_km > 0 else None
        hours, remainder = divmod(duration_s, 3600)
        minutes, seconds = divmod(remainder, 60)
        writer.writerow({
            "id": item["id"],
            "activity_date": item["activity_date"],
            "activity_type": item["activity_type"],
            "distance_km": f"{distance_km:.3f}",
            "duration_s": duration_s,
            "duration": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            "pace_seconds_per_km": pace_s if pace_s is not None else "",
            "pace": f"{pace_s // 60}:{pace_s % 60:02d}/km" if pace_s is not None else "",
            "avg_speed_kmh": f"{distance_km * 3600 / duration_s:.3f}" if duration_s > 0 else "",
            "calories": item["calories"] if item["calories"] is not None else "",
            "avg_heart_rate": item["avg_heart_rate"] if item["avg_heart_rate"] is not None else "",
            "shoe": item["shoe_name"] or "",
            "notes": item["notes"] or "",
        })
    filename = f"allenamenti-draft-{date.today().isoformat()}.csv"
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/drafts", response_model=Activity, status_code=status.HTTP_201_CREATED)
def create_draft(payload: ActivityCreate):
    if payload.shoe_id and repository.get_shoe(payload.shoe_id) is None:
        raise HTTPException(status_code=404, detail="Running shoe not found")
    return repository.create_activity(payload, record_status="draft")


@app.patch("/api/drafts/{activity_id}", response_model=Activity)
def update_draft(activity_id: int, payload: ActivityUpdate):
    existing = repository.get_activity(activity_id)
    if existing is None or existing["record_status"] != "draft":
        raise HTTPException(status_code=404, detail="Draft not found")
    if payload.shoe_id and repository.get_shoe(payload.shoe_id) is None:
        raise HTTPException(status_code=404, detail="Running shoe not found")
    return repository.update_activity(activity_id, payload)


@app.get("/api/shoes", response_model=list[RunningShoe])
def running_shoes():
    return repository.list_shoes()


@app.post("/api/shoes", response_model=RunningShoe, status_code=status.HTTP_201_CREATED)
def create_running_shoe(payload:RunningShoeCreate):
    return repository.create_shoe(payload)


@app.patch("/api/shoes/{shoe_id}", response_model=RunningShoe)
def update_running_shoe(shoe_id:int,payload:RunningShoeUpdate):
    item=repository.update_shoe(shoe_id,payload)
    if item is None:raise HTTPException(404,"Running shoe not found")
    return item


@app.post("/api/shoes/{shoe_id}/photo", response_model=RunningShoe)
async def upload_shoe_photo(shoe_id:int,file:UploadFile=File(...)):
    if repository.get_shoe(shoe_id) is None:raise HTTPException(404,"Running shoe not found")
    content=await file.read(8*1024*1024+1)
    if len(content)>8*1024*1024:raise HTTPException(413,"Image exceeds 8 MB")
    signatures=[(b"\xff\xd8\xff",".jpg"),(b"\x89PNG\r\n\x1a\n",".png"),(b"RIFF",".webp")]
    suffix=next((ext for signature,ext in signatures if content.startswith(signature)),None)
    if suffix==".webp" and content[8:12]!=b"WEBP":suffix=None
    if not suffix:raise HTTPException(415,"Only JPEG, PNG and WebP images are accepted")
    directory=get_settings().data_dir/"shoes";directory.mkdir(parents=True,exist_ok=True);filename=f"{secrets.token_hex(16)}{suffix}";destination=directory/filename
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL;descriptor=os.open(destination,flags,0o640)
    try:
        with os.fdopen(descriptor,"wb") as output:output.write(content)
        previous=repository.set_shoe_photo(shoe_id,filename)
        if previous:(directory/previous).unlink(missing_ok=True)
    except Exception:destination.unlink(missing_ok=True);raise
    return repository.get_shoe(shoe_id)


@app.get("/api/shoes/{shoe_id}/photo")
def shoe_photo(shoe_id:int):
    shoe=repository.get_shoe(shoe_id)
    if not shoe or not shoe["photo_filename"]:raise HTTPException(404,"Photo not found")
    directory=(get_settings().data_dir/"shoes").resolve();path=(directory/shoe["photo_filename"]).resolve()
    if directory not in path.parents or not path.is_file():raise HTTPException(404,"Photo not found")
    return FileResponse(path)


@app.delete("/api/shoes/{shoe_id}",status_code=status.HTTP_204_NO_CONTENT)
def delete_running_shoe(shoe_id:int):
    item=repository.delete_shoe(shoe_id)
    if item is None:raise HTTPException(404,"Running shoe not found")
    if item["photo_filename"]:(get_settings().data_dir/"shoes"/item["photo_filename"]).unlink(missing_ok=True)


@app.delete("/api/drafts/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(activity_id: int):
    existing = repository.get_activity(activity_id)
    if existing is None or existing["record_status"] != "draft" or not repository.delete_activity(activity_id):
        raise HTTPException(status_code=404, detail="Draft not found")


@app.get("/api/drafts/trend")
def draft_trend(sport: ActivityType | None = Query(None)):
    return repository.chart_data("week", sport=sport, record_status="draft")


@app.get("/api/planned-workouts", response_model=list[PlannedWorkout])
def planned_workouts(start: date = Query(...), end: date = Query(...)):
    if end < start or (end - start).days > 62:
        raise HTTPException(status_code=422, detail="Invalid date range")
    return repository.list_planned(start, end)


@app.post("/api/planned-workouts", response_model=PlannedWorkout, status_code=status.HTTP_201_CREATED)
def create_planned_workout(payload: PlannedWorkoutCreate):
    return repository.create_planned(payload)


@app.patch("/api/planned-workouts/{planned_id}", response_model=PlannedWorkout)
def update_planned_workout(planned_id: int, payload: PlannedWorkoutUpdate):
    item = repository.update_planned(planned_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Planned workout not found")
    return item


@app.delete("/api/planned-workouts/{planned_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_planned_workout(planned_id: int):
    if not repository.delete_planned(planned_id):
        raise HTTPException(status_code=404, detail="Planned workout not found")


@app.get("/api/coach/status")
def coach_status():
    settings = get_settings()
    return {"configured": ai_coach.configured(), "model": settings.openai_model}


def _coach_context(payload: CoachPlanRequest) -> dict:
    history_start = payload.week_start - timedelta(days=56)
    history_end = payload.week_start - timedelta(days=1)
    raw_activities = repository.coach_recent_activities(history_start, history_end)
    # The official entry and its manually recorded draft describe the same workout
    # when date, sport, distance and duration are identical. Repository ordering
    # puts verified first, so the official record wins while unmatched drafts remain.
    unique: dict[tuple, dict] = {}
    for item in raw_activities:
        key = (item["activity_date"], item["activity_type"], item["distance_m"], item["duration_s"])
        unique.setdefault(key, item)
    activities = list(unique.values())
    weekly: dict[str, dict] = {}
    compact_activities = []
    for item in activities:
        activity_date = date.fromisoformat(item["activity_date"])
        monday = activity_date - timedelta(days=activity_date.weekday())
        bucket = weekly.setdefault(monday.isoformat(), {"sessions": 0, "distance_m": 0, "duration_s": 0})
        bucket["sessions"] += 1
        bucket["distance_m"] += item["distance_m"]
        bucket["duration_s"] += item["duration_s"]
        compact_activities.append({
            "date": item["activity_date"], "sport": item["activity_type"],
            "distance_m": item["distance_m"], "duration_s": item["duration_s"],
            "avg_heart_rate": item["avg_heart_rate"], "status": item["record_status"],
            "notes": (item["notes"] or "")[:300],
        })
    race_end = payload.week_start + timedelta(days=90)
    races = [
        {"date": item["race_date"], "name": item["name"], "distance_m": item["distance_m"], "location": item["location"]}
        for item in repository.list_races(payload.week_start, race_end) if item["registered"]
    ]
    week_end = payload.week_start + timedelta(days=6)
    existing = [
        {"date": item["planned_date"], "sport": item["activity_type"], "title": item["title"], "status": item["status"]}
        for item in repository.list_planned(payload.week_start, week_end)
    ]
    shoe_items = repository.list_shoes()
    shoes = [
        {"name": item["name"], "active": item["active"], "distance_m": item["distance_m"], "remaining_m": item["remaining_m"]}
        for item in shoe_items if item["active"]
    ]
    scale_items = repository.list_scale_entries(12)
    scale = None
    if scale_items:
        item = scale_items[0]
        scale = {key: item[key] for key in ("measured_date", "weight_kg", "body_fat_percent", "bmi")}
    return {
        "history_range": {"start": history_start.isoformat(), "end": history_end.isoformat()},
        "weekly_totals": [{"week_start": key} | value for key, value in sorted(weekly.items())],
        "recent_activities": compact_activities,
        "confirmed_races": races,
        "existing_week_plan": existing,
        "active_shoes": shoes,
        "latest_scale_entry": scale,
        "recent_scale_entries": [
            {key: item[key] for key in ("measured_date", "weight_kg", "body_fat_percent", "bmi")}
            for item in scale_items
        ],
    }


@app.post("/api/coach/feedback", response_model=CoachFeedback)
def coach_feedback(payload: CoachFeedbackRequest):
    if not ai_coach.configured():
        raise HTTPException(status_code=503, detail="Coach AI non configurato: aggiungi OPENAI_API_KEY sul server")
    today = date.today()
    next_monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
    context_request = CoachPlanRequest(week_start=next_monday, sessions=1)
    try:
        return ai_coach.generate_feedback(payload, _coach_context(context_request))
    except ai_coach.CoachError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/coach/plan", response_model=CoachPlan)
def coach_plan(payload: CoachPlanRequest):
    if not ai_coach.configured():
        raise HTTPException(status_code=503, detail="Coach AI non configurato: aggiungi OPENAI_API_KEY sul server")
    try:
        plan = ai_coach.generate_plan(payload, _coach_context(payload))
    except ai_coach.CoachError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if payload.available_days:
        allowed = {list(("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")).index(day) for day in payload.available_days}
        if any(item.planned_date.weekday() not in allowed for item in plan.workouts):
            raise HTTPException(status_code=502, detail="Il piano non rispetta i giorni disponibili")
    return plan


@app.post("/api/coach/accept", response_model=CoachAcceptResult, status_code=status.HTTP_201_CREATED)
def accept_coach_plan(payload: CoachPlan):
    week_end = payload.week_start + timedelta(days=6)
    existing_dates = {item["planned_date"] for item in repository.list_planned(payload.week_start, week_end)}
    conflicts = [item.planned_date.isoformat() for item in payload.workouts if item.planned_date.isoformat() in existing_dates]
    if conflicts:
        raise HTTPException(status_code=409, detail=f"Esiste già un allenamento il {', '.join(conflicts)}")
    intensity_names = {"recovery": "Recupero", "easy": "Facile", "moderate": "Moderato", "hard": "Intenso", "long": "Lungo"}
    items = [PlannedWorkoutCreate(
        planned_date=item.planned_date,
        activity_type=item.activity_type,
        title=item.title,
        target_distance_m=item.target_distance_m,
        target_duration_s=item.target_duration_s,
        notes=f"Coach AI · {intensity_names[item.intensity]}\n{item.notes}\n\nPerché: {item.rationale}".strip(),
        status="planned",
    ) for item in payload.workouts]
    return {"created": repository.create_planned_many(items)}


@app.get("/api/planned-races", response_model=list[PlannedRace])
def planned_races(start: date = Query(...), end: date = Query(...)):
    if end < start or (end - start).days > 370:
        raise HTTPException(status_code=422, detail="Invalid date range")
    return repository.list_races(start, end)


@app.post("/api/planned-races", response_model=PlannedRace, status_code=status.HTTP_201_CREATED)
def create_planned_race(payload: PlannedRaceCreate):
    return repository.create_race(payload)


@app.patch("/api/planned-races/{race_id}", response_model=PlannedRace)
def update_planned_race(race_id: int, payload: PlannedRaceUpdate):
    item = repository.update_race(race_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return item


@app.delete("/api/planned-races/{race_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_planned_race(race_id: int):
    if not repository.delete_race(race_id):
        raise HTTPException(status_code=404, detail="Race not found")


@app.get("/api/scale-entries", response_model=list[ScaleEntry])
def scale_entries(limit: int = Query(500, ge=1, le=2000)):
    return repository.list_scale_entries(limit)


@app.post("/api/scale-entries", response_model=ScaleEntry, status_code=status.HTTP_201_CREATED)
def create_scale_entry(payload: ScaleEntryCreate):
    return repository.create_scale_entry(payload)


@app.patch("/api/scale-entries/{entry_id}", response_model=ScaleEntry)
def update_scale_entry(entry_id: int, payload: ScaleEntryUpdate):
    item = repository.update_scale_entry(entry_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Scale entry not found")
    return item


@app.delete("/api/scale-entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scale_entry(entry_id: int):
    if not repository.delete_scale_entry(entry_id):
        raise HTTPException(status_code=404, detail="Scale entry not found")


@app.get("/api/sports-documents", response_model=SportsDocuments)
def sports_documents():
    return repository.get_sports_documents()


@app.put("/api/sports-documents", response_model=SportsDocuments)
def update_sports_documents(payload: SportsDocumentsUpdate):
    return repository.update_sports_documents(payload)


@app.post("/api/import/strava-batch", status_code=status.HTTP_201_CREATED)
async def import_strava_batch(
    files: list[UploadFile] = File(...),
    start_date: date = Query(..., description="Importa attività con data uguale o successiva"),
):
    if not files:
        raise HTTPException(status_code=400, detail="Seleziona almeno uno ZIP Strava")
    reports: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="running-strava-") as temp_name:
        temp_root = Path(temp_name)
        for index, upload in enumerate(files):
            filename = Path(upload.filename or "").name
            if Path(filename).suffix.lower() != ".zip":
                raise HTTPException(status_code=415, detail=f"{filename or 'File'}: serve un archivio ZIP")
            archive_path = temp_root / f"upload-{index}.zip"
            size = 0
            with archive_path.open("wb") as destination:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_STRAVA_ZIP_BYTES:
                        raise HTTPException(status_code=413, detail=f"{filename}: ZIP superiore a 1 GB")
                    destination.write(chunk)
            await upload.close()
            extract_dir = temp_root / f"export-{index}"
            extract_dir.mkdir()
            try:
                _safe_extract_zip(archive_path, extract_dir)
            except (zipfile.BadZipFile, ValueError) as exc:
                raise HTTPException(status_code=400, detail=f"{filename}: {exc}") from exc
            csv_files = sorted(extract_dir.rglob("activities.csv"), key=lambda path: len(path.parts))
            if not csv_files:
                raise HTTPException(status_code=400, detail=f"{filename}: activities.csv non trovato")
            report = import_export(
                csv_files[0].parent,
                start_date=start_date,
                source_name=Path(filename).stem,
            )
            reports.append(report.as_dict())
    totals = {
        key: sum(int(report[key]) for report in reports)
        for key in ("total", "imported", "duplicate", "missing_file", "skipped_before_date")
    }
    totals["errors"] = sum(len(report["errors"]) for report in reports)
    return {"start_date": start_date.isoformat(), "reports": reports, "totals": totals}


@app.get("/api/intervals/status")
def intervals_status():
    return intervals_configuration()


def _intervals_preview(start_date: date, end_date: date) -> list[dict]:
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="La data iniziale deve precedere quella finale")
    try:
        activities = intervals_activities(start_date, end_date)
    except IntervalsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    for activity in activities:
        duplicate = repository.external_duplicate(activity)
        activity["duplicate"] = bool(duplicate)
        activity["duplicate_reason"] = duplicate["reason"] if duplicate else None
        activity["duplicate_id"] = duplicate["id"] if duplicate else None
    return activities


def _intervals_file_metadata(activity: dict) -> dict | None:
    downloaded = intervals_activity_file(activity["external_id"], activity.get("file_type"))
    if downloaded is None:
        return None
    content, extension = downloaded
    digest = sha256(content).hexdigest()
    compressed = content.startswith(b"\x1f\x8b")
    suffix = f".{extension}.gz" if compressed else f".{extension}"
    stored_name = f"{digest}{suffix}"
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    destination = settings.upload_dir / stored_name
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
    except FileExistsError:
        pass
    return {
        "original_filename": f"{activity['external_id']}{suffix}",
        "original_file_path": stored_name,
        "original_file_hash": digest,
    }


@app.get("/api/intervals/preview")
def preview_intervals(start_date: date = Query(...), end_date: date = Query(...)):
    activities = _intervals_preview(start_date, end_date)
    return {"activities": activities, "total": len(activities), "new": sum(not item["duplicate"] for item in activities), "duplicates": sum(item["duplicate"] for item in activities)}


@app.post("/api/intervals/import", status_code=status.HTTP_201_CREATED)
def import_intervals(start_date: date = Query(...), end_date: date = Query(...)):
    activities = _intervals_preview(start_date, end_date)
    imported = []
    files_attached = 0
    try:
        for item in activities:
            if not item["duplicate"]:
                metadata = _intervals_file_metadata(item)
                imported.append(repository.import_external_activity(item, file_metadata=metadata))
                files_attached += int(metadata is not None)
            elif item["duplicate_reason"] == "id":
                file_info = repository.get_activity_file(item["duplicate_id"])
                if file_info and not file_info["original_file_path"]:
                    metadata = _intervals_file_metadata(item)
                    if metadata and repository.attach_activity_file(item["duplicate_id"], metadata):
                        files_attached += 1
    except IntervalsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "imported": len(imported), "duplicates": len(activities) - len(imported),
        "files_attached": files_attached, "ids": [item["id"] for item in imported],
    }


@app.post("/api/import", response_model=ImportResult, status_code=status.HTTP_201_CREATED)
async def stage_import(
    file: UploadFile = File(...),
    activity_date: date = Query(...),
    distance_m: int = Query(..., ge=0),
    duration_s: int = Query(..., gt=0),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".fit", ".gpx"}:
        raise HTTPException(status_code=415, detail="Only FIT and GPX files are accepted")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 25 MB")
    digest = sha256(content).hexdigest()
    if repository.hash_exists(digest):
        raise HTTPException(status_code=409, detail="File already imported")
    settings = get_settings()
    stored_name = f"{digest}{suffix}"
    destination = settings.upload_dir / stored_name
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(destination, flags, 0o640)
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
        item = repository.create_activity(
            ActivityCreate(activity_date=activity_date, distance_m=distance_m, duration_s=duration_s),
            {"original_filename": Path(file.filename or stored_name).name,
             "original_file_path": stored_name, "original_file_hash": digest},
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return ImportResult(id=item["id"], filename=item["original_filename"], sha256=digest)
