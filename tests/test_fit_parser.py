import struct

from app.fit_parser import parse_fit_records


def test_minimal_fit_record_parses_gps_and_sensors():
    definition = bytes([0x40, 0, 0]) + struct.pack("<H", 20) + bytes([
        5,
        0, 4, 0x85,   # position_lat: sint32
        1, 4, 0x85,   # position_long: sint32
        3, 1, 0x02,   # heart rate: uint8
        4, 1, 0x02,   # cadence: uint8
        7, 2, 0x84,   # power: uint16
    ])
    message = bytes([0]) + struct.pack("<iiBBH", round(45 / 180 * 2**31), round(9 / 180 * 2**31), 155, 88, 240)
    body = definition + message
    header = bytes([12, 0x20]) + struct.pack("<H", 100) + struct.pack("<I", len(body)) + b".FIT"
    records = parse_fit_records(header + body)
    assert len(records) == 1
    assert round(records[0]["lat"], 5) == 45
    assert round(records[0]["lon"], 5) == 9
    assert records[0]["hr"] == 155
    assert records[0]["cadence"] == 88
    assert records[0]["power"] == 240
