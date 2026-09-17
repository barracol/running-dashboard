from datetime import date, timedelta
import random

from app.db import migrate
from app.repository import create_activity, list_activities
from app.schemas import ActivityCreate


def main() -> None:
    migrate()
    if list_activities(limit=1):
        print("Database già popolato: seed ignorato.")
        return
    random.seed(42)
    today = date.today()
    for weeks_ago, distance in enumerate([5200, 8000, 10400, 6800, 12500, 9100, 15000, 7400]):
        activity_date = today - timedelta(days=weeks_ago * 7 + random.randint(0, 3))
        pace_seconds = random.randint(300, 375)
        create_activity(ActivityCreate(
            activity_date=activity_date, distance_m=distance,
            duration_s=round(distance / 1000 * pace_seconds), calories=round(distance / 1000 * 63),
            avg_heart_rate=random.randint(138, 162), activity_type="running",
            notes="Allenamento demo",
        ))
    print("Create 8 attività demo.")


if __name__ == "__main__":
    main()
