import argparse
import json
from datetime import date
from pathlib import Path

from app.strava_import import import_export


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa uno o più export completi di Strava")
    parser.add_argument("exports", nargs="+", type=Path, help="Cartelle contenenti activities.csv")
    parser.add_argument("--dry-run", action="store_true", help="Analizza senza scrivere nel database")
    parser.add_argument("--start-date", type=date.fromisoformat, help="Importa dalla data inclusa (AAAA-MM-GG)")
    args = parser.parse_args()
    for export in args.exports:
        report = import_export(export, dry_run=args.dry_run, start_date=args.start_date)
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
