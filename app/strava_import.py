from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass, field
from datetime import date, datetime
import gzip
from hashlib import sha256
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from .config import get_settings
from .db import database, migrate


HEADERS = {
    "id": ("Activity ID", "ID attività"),
    "date": ("Activity Date", "Data dell’attività"),
    "name": ("Activity Name", "Nome attività"),
    "type": ("Activity Type", "Tipo attività"),
    "description": ("Activity Description", "Descrizione dell’attività"),
    "private_note": ("Activity Private Note", "Nota privata sulle attività"),
    "elapsed": ("Elapsed Time", "Tempo trascorso"),
    "moving": ("Moving Time", "Tempo in movimento"),
    "distance": ("Distance", "Distanza"),
    "heart_rate": ("Average Heart Rate", "Frequenza cardiaca media"),
    "calories": ("Calories", "Calorie"),
    "filename": ("Filename", "Nome del file"),
}

SPORTS = {
    "run": "running", "corsa": "running",
    "trail run": "trail_running", "corsa su sentiero": "trail_running",
    "walk": "walking", "camminata": "walking",
    "hike": "hiking", "escursione": "hiking",
    "ride": "cycling", "virtual ride": "cycling", "ciclismo": "cycling",
    "mountain bike ride": "mountain_biking", "mountain bike": "mountain_biking",
    "swim": "swimming", "nuotata": "swimming", "nuoto": "swimming",
    "rowing": "rowing", "canottaggio": "rowing",
    "kayaking": "kayaking", "kayak": "kayaking",
    "alpine ski": "skiing", "sci alpino": "skiing",
    "nordic ski": "cross_country_skiing", "sci di fondo": "cross_country_skiing",
    "workout": "workout", "allenamento generico": "workout",
    "yoga": "yoga", "soccer": "football", "calcio": "football",
    "tennis": "tennis", "water sport": "kayaking", "sport acquatico": "kayaking",
}

ITALIAN_MONTHS = {
    "gen": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr", "mag": "May", "giu": "Jun",
    "lug": "Jul", "ago": "Aug", "set": "Sep", "ott": "Oct", "nov": "Nov", "dic": "Dec",
}


@dataclass
class ImportReport:
    source: str
    total: int = 0
    imported: int = 0
    duplicate: int = 0
    missing_file: int = 0
    skipped_before_date: int = 0
    errors: list[str] = field(default_factory=list)
    sports: Counter = field(default_factory=Counter)

    def as_dict(self) -> dict:
        return {
            "source": self.source, "total": self.total, "imported": self.imported,
            "duplicate": self.duplicate, "missing_file": self.missing_file,
            "skipped_before_date": self.skipped_before_date,
            "errors": self.errors, "sports": dict(self.sports),
        }


def _value(row: dict[str, str], key: str) -> str:
    return next((row.get(header, "").strip() for header in HEADERS[key] if row.get(header, "").strip()), "")


def _number(value: str) -> float | None:
    try:
        return float(value.replace(",", ".")) if value else None
    except ValueError:
        return None


def _heart_rate(value: str) -> int | None:
    heart_rate = _number(value)
    return round(heart_rate) if heart_rate is not None and 20 <= heart_rate <= 250 else None


def _date(value: str) -> str:
    normalized = value
    for italian, english in ITALIAN_MONTHS.items():
        normalized = normalized.replace(f" {italian} ", f" {english} ")
    for pattern in ("%b %d, %Y, %I:%M:%S %p", "%d %b %Y, %H:%M:%S"):
        try:
            return datetime.strptime(normalized, pattern).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"data non riconosciuta: {value}")


def _file_digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gpx_sport(path: Path) -> str | None:
    if not (path.name.lower().endswith(".gpx") or path.name.lower().endswith(".gpx.gz")):
        return None
    opener = gzip.open if path.suffix.lower() == ".gz" else open
    try:
        with opener(path, "rb") as stream:
            root = ET.parse(stream).getroot()
        activity_type = next(
            (element.text.casefold() for element in root.iter()
             if element.tag.rsplit("}", 1)[-1] == "type" and element.text),
            None,
        )
        return {"strolling": "walking", "walking": "walking", "running": "running", "cycling": "cycling"}.get(activity_type)
    except (OSError, ET.ParseError):
        return None


def inspect_export(export_dir: Path, start_date: date | None = None) -> ImportReport:
    return import_export(export_dir, dry_run=True, start_date=start_date)


def import_export(
    export_dir: Path,
    dry_run: bool = False,
    start_date: date | None = None,
    source_name: str | None = None,
) -> ImportReport:
    export_dir = export_dir.resolve()
    csv_path = export_dir / "activities.csv"
    if not csv_path.is_file():
        raise FileNotFoundError(f"activities.csv non trovato in {export_dir}")
    source = f"strava:{source_name or export_dir.name}"
    report = ImportReport(source=source)
    settings = get_settings()
    if not dry_run:
        migrate()
        settings.upload_dir.mkdir(parents=True, exist_ok=True)

    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    report.total = len(rows)

    connection_context = database() if not dry_run else None
    db = connection_context.__enter__() if connection_context else None
    try:
        for line, row in enumerate(rows, start=2):
            try:
                activity_date = _date(_value(row, "date"))
                if start_date and date.fromisoformat(activity_date) < start_date:
                    report.skipped_before_date += 1
                    continue
                activity_id = _value(row, "id")
                filename = _value(row, "filename")
                source_file = (export_dir / filename).resolve() if filename else None
                if source_file and export_dir not in source_file.parents:
                    raise ValueError("percorso file esterno all'export")
                sport = (_gpx_sport(source_file) if source_file and source_file.is_file() else None) or SPORTS.get(
                    _value(row, "type").casefold(), "other"
                )
                report.sports[sport] += 1
                digest = _file_digest(source_file) if source_file and source_file.is_file() else None
                if filename and digest is None:
                    report.missing_file += 1
                if db and db.execute(
                    "SELECT 1 FROM activities WHERE (? != '' AND source LIKE 'strava:%' AND source_activity_id = ?) OR (? IS NOT NULL AND original_file_hash = ?)",
                    (activity_id, activity_id, digest, digest),
                ).fetchone():
                    report.duplicate += 1
                    continue
                moving = _number(_value(row, "moving"))
                elapsed = _number(_value(row, "elapsed"))
                duration = round(moving or elapsed or 0)
                if duration <= 0:
                    raise ValueError("durata mancante o non valida")
                destination_name = f"{digest}{''.join(source_file.suffixes)}" if digest and source_file else None
                notes = "\n".join(filter(None, [_value(row, "description"), _value(row, "private_note")]))
                if db:
                    if source_file and destination_name:
                        destination = settings.upload_dir / destination_name
                        if not destination.exists():
                            shutil.copyfile(source_file, destination)
                    db.execute(
                        """INSERT INTO activities
                           (activity_date, distance_m, duration_s, calories, avg_heart_rate, activity_type, notes,
                            original_filename, original_file_path, original_file_hash, source, source_activity_id,
                            activity_name, elapsed_s)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (activity_date, round(_number(_value(row, "distance")) or 0), duration,
                         round(_number(_value(row, "calories"))) if _number(_value(row, "calories")) is not None else None,
                         _heart_rate(_value(row, "heart_rate")),
                         sport, notes, Path(filename).name if filename else None, destination_name, digest,
                         source, activity_id, _value(row, "name"), round(elapsed) if elapsed else None),
                    )
                report.imported += 1
            except Exception as exc:
                report.errors.append(f"riga {line}: {exc}")
    except Exception:
        if connection_context:
            connection_context.__exit__(*__import__("sys").exc_info())
        raise
    else:
        if connection_context:
            connection_context.__exit__(None, None, None)
    return report
