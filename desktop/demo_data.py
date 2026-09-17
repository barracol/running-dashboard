"""Deterministic, disposable sample data for the desktop Demo profile."""

from __future__ import annotations

from datetime import date, timedelta
import random

from app.config import reset_desktop_profile, set_desktop_profile
from app.db import database, migrate


def ensure_demo_data() -> None:
    token = set_desktop_profile("demo")
    try:
        migrate()
        with database() as db:
            if db.execute("SELECT 1 FROM activities LIMIT 1").fetchone():
                return

            rng = random.Random(2408)
            today = date.today()
            shoe_id = db.execute(
                """INSERT INTO running_shoes
                   (name, brand, model, max_distance_m, manual_distance_m, active)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                ("Daily Trainer", "Demo", "Road One", 750_000, 82_000),
            ).lastrowid

            sports = (
                ("running", 5_000, 14_000, 285, 355),
                ("cycling", 24_000, 58_000, 85, 125),
                ("swimming", 1_200, 2_600, 120, 155),
            )
            for index in range(42):
                sport, low, high, pace_low, pace_high = sports[index % len(sports)]
                distance = rng.randrange(low // 100, high // 100) * 100
                duration = round(distance / 1000 * rng.randint(pace_low, pace_high))
                if sport == "swimming":
                    duration = round(distance / 100 * rng.randint(105, 145))
                db.execute(
                    """INSERT INTO activities
                       (activity_date, distance_m, duration_s, calories, avg_heart_rate,
                        activity_type, notes, shoe_id, record_status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'verified')""",
                    (
                        (today - timedelta(days=index * 2)).isoformat(),
                        distance,
                        duration,
                        round(duration / 60 * rng.uniform(7, 11)),
                        rng.randint(126, 164),
                        sport,
                        "Attività dimostrativa",
                        shoe_id if sport == "running" else None,
                    ),
                )

            for index, (title, sport, distance) in enumerate((
                ("Corsa facile", "running", 7_000),
                ("Tecnica e ripetute", "swimming", 1_800),
                ("Giro endurance", "cycling", 42_000),
                ("Progressivo", "running", 10_000),
                ("Recupero attivo", "swimming", 1_400),
            )):
                db.execute(
                    """INSERT INTO planned_workouts
                       (planned_date, activity_type, title, target_distance_m, target_duration_s, notes)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    ((today + timedelta(days=index)).isoformat(), sport, title, distance, None, "Planning demo"),
                )

            db.execute(
                """INSERT INTO planned_races
                   (race_date, name, location, distance_m, cost_cents, website_url, notes, registered)
                   VALUES (?, ?, ?, ?, ?, '', ?, 1)""",
                ((today + timedelta(days=54)).isoformat(), "Mezza di Primavera", "Città Demo", 21_097, 3800, "Gara dimostrativa"),
            )

            for weeks_ago in range(12, -1, -1):
                progress = (12 - weeks_ago) / 12
                db.execute(
                    """INSERT INTO scale_entries
                       (measured_date, weight_kg, body_fat_percent, muscle_mass_kg,
                        water_percent, bmi, visceral_fat, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        (today - timedelta(days=weeks_ago * 7)).isoformat(),
                        round(74.6 - progress * 2.3 + rng.uniform(-0.25, 0.25), 1),
                        round(18.2 - progress * 1.7 + rng.uniform(-0.2, 0.2), 1),
                        round(49.0 + progress * 0.8 + rng.uniform(-0.15, 0.15), 1),
                        round(59.1 + progress * 1.2 + rng.uniform(-0.2, 0.2), 1),
                        round(24.9 - progress * 0.8, 1),
                        7 if weeks_ago > 5 else 6,
                        "Dato dimostrativo",
                    ),
                )
    finally:
        reset_desktop_profile(token)
