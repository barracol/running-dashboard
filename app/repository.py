from datetime import date
import sqlite3

from .db import database
from .schemas import ActivityCreate, ActivityUpdate

PUBLIC_COLUMNS = "id, activity_date, distance_m, duration_s, calories, avg_heart_rate, activity_type, notes, shoe_id, original_filename, original_file_hash, activity_name, elapsed_s, source, record_status, created_at, updated_at"


def _row(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def _filters(sport: str | None, record_status: str = "verified") -> tuple[str, tuple]:
    clauses = ["record_status = ?"]
    params: list[str] = [record_status]
    if sport:
        clauses.append("activity_type = ?")
        params.append(sport)
    return " WHERE " + " AND ".join(clauses), tuple(params)


def list_activities(limit: int = 100, offset: int = 0, sport: str | None = None, record_status: str = "verified") -> list[dict]:
    where, params = _filters(sport, record_status)
    with database() as db:
        rows = db.execute(
            f"SELECT {PUBLIC_COLUMNS} FROM activities{where} ORDER BY activity_date DESC, id DESC LIMIT ? OFFSET ?",
            params + (limit, offset),
        ).fetchall()
    return [dict(row) for row in rows]


def list_drafts_for_export() -> list[dict]:
    """Return every manual activity in chronological order for portable exports."""
    with database() as db:
        rows = db.execute(
            """SELECT a.id, a.activity_date, a.activity_type, a.distance_m,
                      a.duration_s, a.calories, a.avg_heart_rate, a.notes,
                      s.name AS shoe_name
               FROM activities AS a
               LEFT JOIN running_shoes AS s ON s.id = a.shoe_id
               WHERE a.record_status = 'draft'
               ORDER BY a.activity_date, a.id"""
        ).fetchall()
    return [dict(row) for row in rows]


def coach_recent_activities(start: date, end: date) -> list[dict]:
    with database() as db:
        rows = db.execute(
            """SELECT id, activity_date, distance_m, duration_s, avg_heart_rate,
                      activity_type, notes, record_status
               FROM activities
               WHERE activity_date BETWEEN ? AND ?
               ORDER BY activity_date, CASE record_status WHEN 'verified' THEN 0 ELSE 1 END, id""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    return [dict(row) for row in rows]


def get_activity(activity_id: int) -> dict | None:
    with database() as db:
        row = db.execute(f"SELECT {PUBLIC_COLUMNS} FROM activities WHERE id = ?", (activity_id,)).fetchone()
    return _row(row)


def get_activity_file(activity_id: int) -> dict | None:
    with database() as db:
        row = db.execute(
            "SELECT original_filename, original_file_path FROM activities WHERE id = ?", (activity_id,)
        ).fetchone()
    return _row(row)


def create_activity(activity: ActivityCreate, file_metadata: dict | None = None, record_status: str = "verified") -> dict:
    values = activity.model_dump(mode="json")
    file_metadata = file_metadata or {}
    with database() as db:
        cursor = db.execute(
            """INSERT INTO activities
               (activity_date, distance_m, duration_s, calories, avg_heart_rate, activity_type, notes, shoe_id,
                original_filename, original_file_path, original_file_hash, record_status)
               VALUES (:activity_date, :distance_m, :duration_s, :calories, :avg_heart_rate, :activity_type, :notes, :shoe_id,
                       :original_filename, :original_file_path, :original_file_hash, :record_status)""",
            values | {"original_filename": None, "original_file_path": None, "original_file_hash": None,
                      "record_status": record_status} | file_metadata,
        )
        activity_id = cursor.lastrowid
    return get_activity(activity_id)  # type: ignore[return-value]


def external_duplicate(activity: dict, source: str = "intervals.icu") -> dict | None:
    with database() as db:
        exact = db.execute("SELECT id FROM activities WHERE record_status = 'verified' AND source = ? AND source_activity_id = ?", (source, activity["external_id"])).fetchone()
        if exact:
            return {"id": exact["id"], "reason": "id"}
        close = db.execute(
            """SELECT id FROM activities WHERE record_status = 'verified'
               AND activity_date = ? AND activity_type = ?
               AND ABS(distance_m - ?) <= 50 AND ABS(duration_s - ?) <= 10 ORDER BY id LIMIT 1""",
            (activity["activity_date"], activity["activity_type"], activity["distance_m"], activity["duration_s"]),
        ).fetchone()
    return {"id": close["id"], "reason": "dati"} if close else None


def import_external_activity(activity: dict, source: str = "intervals.icu") -> dict:
    with database() as db:
        cursor = db.execute(
            """INSERT INTO activities
               (activity_date, distance_m, duration_s, calories, avg_heart_rate, activity_type, notes, shoe_id,
                activity_name, elapsed_s, source, source_activity_id, record_status)
               VALUES (?, ?, ?, ?, ?, ?, '', NULL, ?, ?, ?, ?, 'verified')""",
            (activity["activity_date"], activity["distance_m"], activity["duration_s"], activity["calories"],
             activity["avg_heart_rate"], activity["activity_type"], activity["activity_name"], activity["elapsed_s"], source, activity["external_id"]),
        )
        activity_id = cursor.lastrowid
    return get_activity(activity_id)  # type: ignore[return-value]


def update_activity(activity_id: int, patch: ActivityUpdate) -> dict | None:
    values = patch.model_dump(exclude_unset=True, mode="json")
    if not values:
        return get_activity(activity_id)
    assignments = ", ".join(f"{key} = :{key}" for key in values)
    with database() as db:
        cursor = db.execute(
            f"UPDATE activities SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = :id",
            values | {"id": activity_id},
        )
        if cursor.rowcount == 0:
            return None
    return get_activity(activity_id)


def delete_activity(activity_id: int) -> bool:
    with database() as db:
        cursor = db.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
    return cursor.rowcount > 0


def list_shoes() -> list[dict]:
    with database() as db:
        rows=db.execute("""SELECT s.*,COALESCE(SUM(a.distance_m),0) tracked_distance_m,
            COALESCE(SUM(a.duration_s),0) tracked_duration_s,COUNT(a.id) activities
            FROM running_shoes s LEFT JOIN activities a ON a.shoe_id=s.id
            GROUP BY s.id ORDER BY s.active DESC,s.created_at DESC,s.id DESC""").fetchall()
    result=[]
    for row in rows:
        item=dict(row);item["active"]=bool(item["active"]);item["photo_url"]=f"/api/shoes/{item['id']}/photo" if item["photo_filename"] else None
        item["distance_m"]=item["manual_distance_m"]+item["tracked_distance_m"]
        if item["tracked_distance_m"]>0 and item["tracked_duration_s"]>0:
            item["avg_speed_kmh"]=round(item["tracked_distance_m"]*3.6/item["tracked_duration_s"],2)
            item["avg_pace_min_km"]=round(item["tracked_duration_s"]/(item["tracked_distance_m"]/1000)/60,2)
        else:item["avg_speed_kmh"]=item["avg_pace_min_km"]=None
        item["remaining_m"]=max(0,item["max_distance_m"]-item["distance_m"]);item["usage_percent"]=round(item["distance_m"]*100/item["max_distance_m"],1)
        result.append(item)
    return result


def get_shoe(shoe_id:int)->dict|None:
    return next((item for item in list_shoes() if item["id"]==shoe_id),None)


def create_shoe(payload)->dict:
    values=payload.model_dump();values["active"]=int(values["active"])
    with database() as db:cursor=db.execute("INSERT INTO running_shoes(name,brand,model,max_distance_m,manual_distance_m,active) VALUES(:name,:brand,:model,:max_distance_m,:manual_distance_m,:active)",values);shoe_id=cursor.lastrowid
    return get_shoe(shoe_id)


def update_shoe(shoe_id:int,payload)->dict|None:
    values=payload.model_dump(exclude_unset=True)
    if "active" in values:values["active"]=int(values["active"])
    if values:
        assignments=", ".join(f"{key}=:{key}" for key in values)
        with database() as db:cursor=db.execute(f"UPDATE running_shoes SET {assignments},updated_at=CURRENT_TIMESTAMP WHERE id=:id",values|{"id":shoe_id})
        if not cursor.rowcount:return None
    return get_shoe(shoe_id)


def set_shoe_photo(shoe_id:int,filename:str)->str|None:
    with database() as db:
        row=db.execute("SELECT photo_filename FROM running_shoes WHERE id=?",(shoe_id,)).fetchone()
        if not row:return None
        db.execute("UPDATE running_shoes SET photo_filename=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(filename,shoe_id))
    return row["photo_filename"]


def delete_shoe(shoe_id:int)->dict|None:
    with database() as db:
        row=db.execute("SELECT photo_filename FROM running_shoes WHERE id=?",(shoe_id,)).fetchone()
        if not row:return None
        db.execute("DELETE FROM running_shoes WHERE id=?",(shoe_id,))
    return dict(row)


def summary(sport: str | None = None, record_status: str = "verified") -> dict:
    where, params = _filters(sport, record_status)
    with database() as db:
        totals = dict(db.execute(
            f"""SELECT COUNT(*) AS activities, COALESCE(SUM(distance_m), 0) AS distance_m,
                      COALESCE(SUM(duration_s), 0) AS duration_s, COALESCE(SUM(calories), 0) AS calories
               FROM activities{where}""", params
        ).fetchone())
        latest = db.execute(
            f"SELECT activity_date FROM activities{where} ORDER BY activity_date DESC LIMIT 1", params
        ).fetchone()
    totals["latest_activity_date"] = latest[0] if latest else None
    return totals


def chart_data(period: str = "week", sport: str | None = None, record_status: str = "verified") -> list[dict]:
    group_expr = {
        "week": "strftime('%Y-W%W', activity_date)",
        "month": "strftime('%Y-%m', activity_date)",
        "year": "strftime('%Y', activity_date)",
    }[period]
    lookback = {"week": "-12 months", "month": "-60 months", "year": "-25 years"}[period]
    sport_clause = " AND activity_type = ?" if sport else ""
    params = (lookback, record_status, sport) if sport else (lookback, record_status)
    with database() as db:
        rows = db.execute(
            f"""SELECT {group_expr} AS period,
                       ROUND(SUM(distance_m) / 1000.0, 2) AS distance_km,
                       ROUND(SUM(duration_s) / 3600.0, 2) AS duration_hours,
                       ROUND(AVG(CASE WHEN distance_m > 0 THEN duration_s / (distance_m / 1000.0) END) / 60.0, 2) AS avg_pace_min_km,
                       ROUND(CASE WHEN SUM(duration_s) > 0 THEN SUM(distance_m) * 3.6 / SUM(duration_s) END, 2) AS avg_speed_kmh,
                       ROUND(AVG(avg_heart_rate), 1) AS avg_heart_rate
                FROM activities
                WHERE activity_date >= date('now', ?) AND record_status = ?{sport_clause}
                GROUP BY period ORDER BY period""",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def sports_summary() -> list[dict]:
    with database() as db:
        rows = db.execute(
            """SELECT activity_type, COUNT(*) AS activities,
                      COALESCE(SUM(distance_m), 0) AS distance_m,
                      COALESCE(SUM(duration_s), 0) AS duration_s
               FROM activities WHERE record_status = 'verified'
               GROUP BY activity_type ORDER BY activities DESC, activity_type"""
        ).fetchall()
    return [dict(row) for row in rows]


def running_personal_bests() -> list[dict]:
    distances = [("10 km", 10_000), ("Mezza maratona", 21_097), ("Maratona", 42_195)]
    results = []
    with database() as db:
        for label, target_m in distances:
            minimum, maximum = round(target_m * 0.97), round(target_m * 1.03)
            row = db.execute(
                f"""SELECT {PUBLIC_COLUMNS} FROM activities
                    WHERE record_status = 'verified' AND activity_type = 'running' AND distance_m BETWEEN ? AND ?
                    ORDER BY duration_s ASC LIMIT 1""",
                (minimum, maximum),
            ).fetchone()
            results.append({
                "label": label, "target_distance_m": target_m,
                "tolerance_percent": 3, "activity": dict(row) if row else None,
            })
    return results


def hash_exists(sha256: str) -> bool:
    with database() as db:
        return db.execute("SELECT 1 FROM activities WHERE original_file_hash = ?", (sha256,)).fetchone() is not None


def list_planned(start: date, end: date) -> list[dict]:
    with database() as db:
        rows = db.execute(
            "SELECT * FROM planned_workouts WHERE planned_date BETWEEN ? AND ? ORDER BY planned_date, id",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    return [dict(row) for row in rows]


def create_planned(payload) -> dict:
    values = payload.model_dump(mode="json")
    with database() as db:
        cursor = db.execute(
            """INSERT INTO planned_workouts
               (planned_date, activity_type, title, target_distance_m, target_duration_s, notes, status)
               VALUES (:planned_date, :activity_type, :title, :target_distance_m, :target_duration_s, :notes, :status)""",
            values,
        )
        planned_id = cursor.lastrowid
    return get_planned(planned_id)


def create_planned_many(payloads: list) -> list[dict]:
    created_ids: list[int] = []
    with database() as db:
        for payload in payloads:
            values = payload.model_dump(mode="json")
            cursor = db.execute(
                """INSERT INTO planned_workouts
                   (planned_date, activity_type, title, target_distance_m, target_duration_s, notes, status)
                   VALUES (:planned_date, :activity_type, :title, :target_distance_m, :target_duration_s, :notes, :status)""",
                values,
            )
            created_ids.append(cursor.lastrowid)
    return [get_planned(item_id) for item_id in created_ids]


def get_planned(planned_id: int) -> dict | None:
    with database() as db:
        row = db.execute("SELECT * FROM planned_workouts WHERE id = ?", (planned_id,)).fetchone()
    return _row(row)


def update_planned(planned_id: int, payload) -> dict | None:
    values = payload.model_dump(exclude_unset=True, mode="json")
    if not values:
        return get_planned(planned_id)
    assignments = ", ".join(f"{key} = :{key}" for key in values)
    with database() as db:
        cursor = db.execute(
            f"UPDATE planned_workouts SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = :id",
            values | {"id": planned_id},
        )
        if cursor.rowcount == 0:
            return None
    return get_planned(planned_id)


def delete_planned(planned_id: int) -> bool:
    with database() as db:
        cursor = db.execute("DELETE FROM planned_workouts WHERE id = ?", (planned_id,))
    return cursor.rowcount > 0


def list_races(start: date, end: date) -> list[dict]:
    with database() as db:
        rows = db.execute(
            "SELECT * FROM planned_races WHERE race_date BETWEEN ? AND ? ORDER BY race_date, id",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    return [dict(row) | {"registered": bool(row["registered"])} for row in rows]


def get_race(race_id: int) -> dict | None:
    with database() as db:
        row = db.execute("SELECT * FROM planned_races WHERE id = ?", (race_id,)).fetchone()
    return (dict(row) | {"registered": bool(row["registered"])}) if row else None


def create_race(payload) -> dict:
    values = payload.model_dump(mode="json")
    values["registered"] = int(values["registered"])
    with database() as db:
        cursor = db.execute(
            """INSERT INTO planned_races
               (race_date, name, location, distance_m, cost_cents, website_url, notes, registered)
               VALUES (:race_date, :name, :location, :distance_m, :cost_cents, :website_url, :notes, :registered)""",
            values,
        )
        race_id = cursor.lastrowid
    return get_race(race_id)


def update_race(race_id: int, payload) -> dict | None:
    values = payload.model_dump(exclude_unset=True, mode="json")
    if "registered" in values:
        values["registered"] = int(values["registered"])
    if not values:
        return get_race(race_id)
    assignments = ", ".join(f"{key} = :{key}" for key in values)
    with database() as db:
        cursor = db.execute(
            f"UPDATE planned_races SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = :id",
            values | {"id": race_id},
        )
        if cursor.rowcount == 0:
            return None
    return get_race(race_id)


def delete_race(race_id: int) -> bool:
    with database() as db:
        cursor = db.execute("DELETE FROM planned_races WHERE id = ?", (race_id,))
    return cursor.rowcount > 0


def list_scale_entries(limit: int = 500) -> list[dict]:
    with database() as db:
        rows = db.execute(
            "SELECT * FROM scale_entries ORDER BY measured_date DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_scale_entry(entry_id: int) -> dict | None:
    with database() as db:
        row = db.execute("SELECT * FROM scale_entries WHERE id = ?", (entry_id,)).fetchone()
    return _row(row)


def create_scale_entry(payload) -> dict:
    values = payload.model_dump(mode="json")
    with database() as db:
        cursor = db.execute(
            """INSERT INTO scale_entries
               (measured_date, weight_kg, body_fat_percent, muscle_mass_kg, water_percent, bmi, visceral_fat, notes)
               VALUES (:measured_date, :weight_kg, :body_fat_percent, :muscle_mass_kg, :water_percent, :bmi, :visceral_fat, :notes)""",
            values,
        )
        entry_id = cursor.lastrowid
    return get_scale_entry(entry_id)


def update_scale_entry(entry_id: int, payload) -> dict | None:
    values = payload.model_dump(exclude_unset=True, mode="json")
    if not values:
        return get_scale_entry(entry_id)
    assignments = ", ".join(f"{key} = :{key}" for key in values)
    with database() as db:
        cursor = db.execute(
            f"UPDATE scale_entries SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = :id",
            values | {"id": entry_id},
        )
        if cursor.rowcount == 0:
            return None
    return get_scale_entry(entry_id)


def delete_scale_entry(entry_id: int) -> bool:
    with database() as db:
        cursor = db.execute("DELETE FROM scale_entries WHERE id = ?", (entry_id,))
    return cursor.rowcount > 0


def get_sports_documents() -> dict:
    with database() as db:
        row = db.execute("SELECT run_card_number, run_card_expiry, medical_certificate_expiry, updated_at FROM sports_documents WHERE id = 1").fetchone()
    return dict(row)


def update_sports_documents(payload) -> dict:
    values = payload.model_dump(mode="json")
    with database() as db:
        db.execute(
            """UPDATE sports_documents
               SET run_card_number = :run_card_number, run_card_expiry = :run_card_expiry,
                   medical_certificate_expiry = :medical_certificate_expiry,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = 1""",
            values,
        )
    return get_sports_documents()
