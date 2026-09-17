from __future__ import annotations

import gzip
from pathlib import Path
import xml.etree.ElementTree as ET

from .fit_parser import parse_fit_records


def _text(element: ET.Element, name: str) -> str | None:
    child = next((item for item in element.iter() if item.tag.rsplit("}", 1)[-1] == name), None)
    return child.text if child is not None else None


def parse_gpx(path: Path, max_points: int = 1500) -> dict:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        root = ET.parse(stream).getroot()
    raw = []
    for point in root.iter():
        if point.tag.rsplit("}", 1)[-1] != "trkpt":
            continue
        item = {"lat": float(point.attrib["lat"]), "lon": float(point.attrib["lon"])}
        elevation = _text(point, "ele")
        heart_rate = _text(point, "hr")
        timestamp = _text(point, "time")
        if elevation:
            item["ele"] = round(float(elevation), 1)
        if heart_rate:
            item["hr"] = round(float(heart_rate))
        if timestamp:
            item["time"] = timestamp
        raw.append(item)
    return _track_result(raw, "gpx", max_points)


def _track_result(raw: list[dict], file_format: str, max_points: int = 1500) -> dict:
    if not raw:
        return {"status": "no_track", "format": file_format, "points": []}
    if len(raw) > max_points:
        indexes = {round(index * (len(raw) - 1) / (max_points - 1)) for index in range(max_points)}
        points = [raw[index] for index in sorted(indexes)]
    else:
        points = raw
    return {
        "status": "available", "format": file_format, "points": points,
        "original_point_count": len(raw),
        "bounds": {
            "min_lat": min(point["lat"] for point in raw), "max_lat": max(point["lat"] for point in raw),
            "min_lon": min(point["lon"] for point in raw), "max_lon": max(point["lon"] for point in raw),
        },
    }


def _simplify(raw: list[dict], max_points: int) -> list[dict]:
    if len(raw) <= max_points:
        return raw
    indexes = {round(index * (len(raw) - 1) / (max_points - 1)) for index in range(max_points)}
    return [raw[index] for index in sorted(indexes)]


def parse_fit(path: Path, max_points: int = 1500) -> dict:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        records = parse_fit_records(stream.read())
    gps_points = [record for record in records if "lat" in record and "lon" in record]
    result = _track_result(gps_points, "fit", max_points)
    # Outdoor records already carry sensor values in `points`; only indoor FIT files
    # need a separate sample stream. Avoid sending the same data twice.
    result["samples"] = [] if gps_points else _simplify(records, max_points)
    result["original_sample_count"] = len(records)
    return result


def activity_track(path: Path) -> dict:
    suffixes = "".join(path.suffixes).lower()
    if suffixes.endswith(".gpx") or suffixes.endswith(".gpx.gz"):
        return parse_gpx(path)
    if suffixes.endswith(".fit") or suffixes.endswith(".fit.gz"):
        return parse_fit(path)
    return {"status": "unsupported", "format": path.suffix.lstrip("."), "points": []}
