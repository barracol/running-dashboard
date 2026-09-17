#!/usr/bin/env python3
"""Generate a transparent distance/pace chart from a Running Dashboard CSV export."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta
import os
from pathlib import Path
import sys
import tempfile

try:
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "running-dashboard-matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, MaxNLocator
except ImportError as exc:  # pragma: no cover - depends on the caller environment
    raise SystemExit(
        "Matplotlib non installato. Esegui: python3 -m pip install -r requirements-plot.txt"
    ) from exc


def _number(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    return float(value.strip().replace(" ", "").replace(",", "."))


def _duration_seconds(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    parts = [int(part) for part in value.strip().split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return None


def _pace_seconds(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    clean = value.lower().replace("min", "").replace("/km", "").strip()
    parts = clean.split(":")
    if len(parts) != 2:
        return None
    return int(parts[0]) * 60 + int(parts[1])


def _first(row: dict[str, str], *names: str) -> str | None:
    normalized = {key.strip().lower(): value for key, value in row.items() if key}
    return next((normalized[name] for name in names if name in normalized), None)


def load_workouts(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        header = sample.splitlines()[0] if sample else ""
        delimiter = max((";", ",", "\t"), key=header.count)
        rows = csv.DictReader(handle, delimiter=delimiter)
        result = []
        for line_number, row in enumerate(rows, start=2):
            date_value = _first(row, "activity_date", "date", "data")
            distance = _number(_first(row, "distance_km", "distanza_km", "distance"))
            duration_s = _number(_first(row, "duration_s", "durata_s"))
            if duration_s is None:
                duration_s = _duration_seconds(_first(row, "duration", "durata"))
            pace_s = _number(_first(row, "pace_seconds_per_km", "passo_secondi_km"))
            if pace_s is None:
                pace_s = _pace_seconds(_first(row, "pace", "passo"))
            if pace_s is None and distance and duration_s:
                pace_s = duration_s / distance
            if not date_value or distance is None or distance <= 0 or pace_s is None or pace_s <= 0:
                print(f"Riga {line_number} ignorata: data, distanza o passo non validi", file=sys.stderr)
                continue
            try:
                parsed_date = datetime.fromisoformat(date_value.strip()).date()
            except ValueError:
                try:
                    parsed_date = datetime.strptime(date_value.strip(), "%d/%m/%Y").date()
                except ValueError:
                    print(f"Riga {line_number} ignorata: data non riconosciuta", file=sys.stderr)
                    continue
            result.append({"date": parsed_date, "distance_km": distance, "pace_s": pace_s})
    return sorted(result, key=lambda item: item["date"])


def pace_label(value: float, _position=None) -> str:
    seconds = max(0, round(value))
    return f"{seconds // 60}:{seconds % 60:02d}/km"


def duration_label(total_seconds: float) -> str:
    seconds = max(0, round(total_seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def workout_summary(workouts: list[dict]) -> dict:
    total_distance = sum(item["distance_km"] for item in workouts)
    total_seconds = sum(item["pace_s"] * item["distance_km"] for item in workouts)
    average_pace = total_seconds / total_distance if total_distance else 0
    return {
        "distance_km": total_distance,
        "duration_s": total_seconds,
        "workouts": len(workouts),
        "average_pace_s": average_pace,
    }


def group_workouts_by_week(workouts: list[dict]) -> list[dict]:
    """Aggregate sessions by ISO week and calculate a distance-weighted pace."""
    weeks: dict = {}
    for workout in workouts:
        week_start = workout["date"] - timedelta(days=workout["date"].weekday())
        bucket = weeks.setdefault(
            week_start,
            {"date": week_start, "distance_km": 0.0, "duration_s": 0.0, "sessions": 0},
        )
        bucket["distance_km"] += workout["distance_km"]
        bucket["duration_s"] += workout["pace_s"] * workout["distance_km"]
        bucket["sessions"] += 1

    result = []
    for bucket in weeks.values():
        bucket["pace_s"] = bucket["duration_s"] / bucket["distance_km"]
        result.append(bucket)
    return sorted(result, key=lambda item: item["date"])


def week_label(week_start) -> str:
    week_end = week_start + timedelta(days=6)
    if week_start.month == week_end.month:
        return f"{week_start.day}–{week_end.day}/{week_end.month:02d}"
    return f"{week_start.day}/{week_start.month:02d}–{week_end.day}/{week_end.month:02d}"


def plot_workouts(workouts: list[dict], output: Path, title: str, dpi: int) -> None:
    if not workouts:
        raise ValueError("Il CSV non contiene allenamenti validi")
    workouts = group_workouts_by_week(workouts)
    count = len(workouts)
    width = max(10, min(24, 6 + count * 0.62))
    fig, distance_axis = plt.subplots(figsize=(width, 7), layout="constrained")
    fig.patch.set_alpha(0)
    distance_axis.set_facecolor("none")
    pace_axis = distance_axis.twinx()
    pace_axis.set_facecolor("none")

    positions = list(range(count))
    bar_width = 0.38
    lime, cyan, text, grid = "#A7F432", "#43D9C7", "#F5F7F6", "#FFFFFF24"
    distance_bars = distance_axis.bar(
        [position - bar_width / 2 for position in positions],
        [item["distance_km"] for item in workouts],
        width=bar_width, color=lime, label="Distanza", zorder=3,
    )
    pace_bars = pace_axis.bar(
        [position + bar_width / 2 for position in positions],
        [item["pace_s"] for item in workouts],
        width=bar_width, color=cyan, label="Passo", zorder=2,
    )

    labels = [week_label(item["date"]) for item in workouts]
    distance_axis.set_xticks(positions, labels, rotation=35, ha="right", color=text)
    distance_axis.set_ylabel("Distanza (km)", color=lime, fontsize=12, fontweight="bold")
    pace_axis.set_ylabel("Passo medio", color=cyan, fontsize=12, fontweight="bold")
    pace_axis.yaxis.set_major_formatter(FuncFormatter(pace_label))
    distance_axis.yaxis.set_major_locator(MaxNLocator(nbins=6, integer=False))
    pace_axis.yaxis.set_major_locator(MaxNLocator(nbins=6, integer=True))
    distance_axis.tick_params(axis="y", colors=lime)
    pace_axis.tick_params(axis="y", colors=cyan)
    distance_axis.tick_params(axis="x", colors=text)
    distance_axis.grid(axis="y", color=grid, linewidth=1, zorder=0)
    pace_axis.grid(False)
    for axis in (distance_axis, pace_axis):
        for spine in axis.spines.values():
            spine.set_visible(False)

    distance_axis.set_title(title, color=text, fontsize=22, fontweight="bold", loc="left", pad=22)
    distance_axis.bar_label(
        distance_bars,
        labels=[f"{item['distance_km']:.1f} km\n{item['sessions']} all." for item in workouts],
        color=lime, fontsize=8, padding=3, rotation=90,
    )
    pace_axis.bar_label(
        pace_bars,
        labels=[pace_label(item["pace_s"]) for item in workouts],
        color=cyan, fontsize=8, padding=3, rotation=90,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=dpi, transparent=True, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="CSV esportato dalla sezione Draft")
    parser.add_argument("-o", "--output", type=Path, default=Path("allenamenti-draft.png"))
    parser.add_argument("--title", default="ALLENAMENTI DRAFT · SETTIMANE")
    parser.add_argument("--dpi", type=int, default=180)
    args = parser.parse_args()
    try:
        workouts = load_workouts(args.csv)
        plot_workouts(workouts, args.output, args.title, args.dpi)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    summary = workout_summary(workouts)
    print("\nRIEPILOGO COMPLESSIVO")
    print(f"Km percorsi:      {summary['distance_km']:.1f} km")
    print(f"Tempo di corsa:   {duration_label(summary['duration_s'])}")
    print(f"Allenamenti:      {summary['workouts']}")
    print(f"Passo medio:      {pace_label(summary['average_pace_s'])}")
    print(f"Grafico salvato in: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
