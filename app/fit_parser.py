from __future__ import annotations

from datetime import datetime, timedelta, timezone
import struct


class FitParseError(ValueError):
    pass


BASE_TYPES = {
    0: ("B", 1), 1: ("b", 1), 2: ("B", 1), 3: ("h", 2), 4: ("H", 2),
    5: ("i", 4), 6: ("I", 4), 8: ("f", 4), 9: ("d", 8), 10: ("B", 1),
    11: ("H", 2), 12: ("I", 4), 13: ("B", 1), 14: ("q", 8),
    15: ("Q", 8), 16: ("Q", 8),
}

INVALID = {
    0: 0xFF, 1: 0x7F, 2: 0xFF, 3: 0x7FFF, 4: 0xFFFF, 5: 0x7FFFFFFF,
    6: 0xFFFFFFFF, 10: 0, 11: 0, 12: 0, 14: 0x7FFFFFFFFFFFFFFF,
    15: 0xFFFFFFFFFFFFFFFF, 16: 0,
}


def _decode(raw: bytes, base_type: int, endian: str):
    kind = base_type & 0x1F
    if kind == 7:
        return raw.rstrip(b"\0").decode("utf-8", errors="replace")
    spec = BASE_TYPES.get(kind)
    if not spec or len(raw) < spec[1]:
        return None
    fmt, size = spec
    values = struct.unpack(endian + fmt * (len(raw) // size), raw[: len(raw) // size * size])
    value = values[0] if len(values) == 1 else values
    if not isinstance(value, tuple) and value == INVALID.get(kind):
        return None
    return value


def parse_fit_records(data: bytes) -> list[dict]:
    if len(data) < 12:
        raise FitParseError("header FIT incompleto")
    header_size = data[0]
    if header_size < 12 or len(data) < header_size or data[8:12] != b".FIT":
        raise FitParseError("firma FIT non valida")
    data_size = struct.unpack_from("<I", data, 4)[0]
    end = min(header_size + data_size, len(data))
    offset = header_size
    definitions: dict[int, tuple[int, str, list[tuple[int, int, int]], int]] = {}
    records: list[dict] = []
    while offset < end:
        header = data[offset]
        offset += 1
        compressed = bool(header & 0x80)
        if compressed:
            local_number = (header >> 5) & 0x03
            is_definition = False
            has_developer = False
        else:
            local_number = header & 0x0F
            is_definition = bool(header & 0x40)
            has_developer = bool(header & 0x20)
        if is_definition:
            if offset + 5 > end:
                raise FitParseError("definizione FIT incompleta")
            offset += 1  # reserved
            architecture = data[offset]
            offset += 1
            endian = ">" if architecture else "<"
            global_number = struct.unpack_from(endian + "H", data, offset)[0]
            offset += 2
            field_count = data[offset]
            offset += 1
            fields = []
            for _ in range(field_count):
                if offset + 3 > end:
                    raise FitParseError("campo FIT incompleto")
                number, size, base_type = data[offset:offset + 3]
                offset += 3
                fields.append((number, size, base_type))
            developer_size = 0
            if has_developer:
                count = data[offset]
                offset += 1
                for _ in range(count):
                    if offset + 3 > end:
                        raise FitParseError("campo sviluppatore FIT incompleto")
                    developer_size += data[offset + 1]
                    offset += 3
            definitions[local_number] = (global_number, endian, fields, developer_size)
            continue
        definition = definitions.get(local_number)
        if not definition:
            raise FitParseError(f"definizione locale FIT {local_number} mancante")
        global_number, endian, fields, developer_size = definition
        values = {}
        for number, size, base_type in fields:
            if offset + size > end:
                raise FitParseError("messaggio FIT troncato")
            if global_number == 20:
                values[number] = _decode(data[offset:offset + size], base_type, endian)
            offset += size
        offset += developer_size
        if global_number != 20:
            continue
        lat, lon = values.get(0), values.get(1)
        record = {}
        if lat is not None and lon is not None:
            record.update({"lat": lat * 180.0 / 2**31, "lon": lon * 180.0 / 2**31})
        altitude = values.get(78)
        if altitude is not None:
            record["ele"] = round(altitude / 5 - 500, 1)
        elif values.get(2) is not None:
            record["ele"] = round(values[2] / 5 - 500, 1)
        for field, key in ((3, "hr"), (4, "cadence"), (7, "power")):
            if values.get(field) is not None:
                record[key] = values[field]
        speed = values.get(73) if values.get(73) is not None else values.get(6)
        if speed is not None:
            record["speed_m_s"] = round(speed / 1000, 3)
        timestamp = values.get(253)
        if timestamp is not None:
            record["time"] = (datetime(1989, 12, 31, tzinfo=timezone.utc) + timedelta(seconds=timestamp)).isoformat()
        if record:
            records.append(record)
    return records
