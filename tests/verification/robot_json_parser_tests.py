from pathlib import Path

from pyhamilton.verification.models import EventCategory
from pyhamilton.verification.parsers.robot_json_parser import (
    COMMAND_CATEGORY,
    parse_robot_json_log,
)


def write_log(tmp_path, lines):
    path = tmp_path / "robot_json.log"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_parse_robot_json_log_repr_format(tmp_path):
    path = write_log(
        tmp_path,
        [
            "{'command': 'channelAspirate', 'id': '0x2', 'labwarePositions': 'Plate A, A1', 'channelVariable': '1111000000000000', 'volumes': [10]}",
        ],
    )

    events = parse_robot_json_log(path)

    assert len(events) == 1
    assert events[0].category == EventCategory.ASPIRATE
    assert events[0].resources == ["Plate A"]
    assert events[0].volume_ul == 10.0
    assert events[0].head == "head_8ch"
    assert events[0].channel_count == 4


def test_parse_robot_json_log_json_format(tmp_path):
    path = write_log(
        tmp_path,
        [
            '{"command": "channelDispense", "id": "0x1", "labwarePositions": "Plate B, B1", "channelVariable": "1000000000000000", "volumes": [5], "liquidFollowing": false}',
        ],
    )

    events = parse_robot_json_log(path)

    assert len(events) == 1
    assert events[0].category == EventCategory.DISPENSE
    assert events[0].resources == ["Plate B"]


def test_parse_robot_json_log_mixed_format_and_id_ordering(tmp_path):
    path = write_log(
        tmp_path,
        [
            '{"command": "initialize", "id": "0x2"}',
            "{'command': 'channelTipPickUp', 'id': '0x1', 'labwarePositions': 'Tip Rack, 1'}",
        ],
    )

    events = parse_robot_json_log(path)

    assert [event.action for event in events] == ["channelTipPickUp", "initialize"]
    assert [event.sequence for event in events] == [0, 1]


def test_parse_robot_json_log_malformed_line(tmp_path):
    path = write_log(
        tmp_path,
        [
            "not a dict",
            "{'command': 'initialize', 'id': '0x1'}",
        ],
    )

    events = parse_robot_json_log(path)

    assert len(events) == 1
    assert events[0].category == EventCategory.INITIALIZE


def test_parse_robot_json_log_empty_file(tmp_path):
    path = write_log(tmp_path, [])

    assert parse_robot_json_log(path) == []


def test_command_to_category_mapping():
    assert COMMAND_CATEGORY["initialize"] == EventCategory.INITIALIZE
    assert COMMAND_CATEGORY["channelTipPickUp"] == EventCategory.TIP_PICKUP
    assert COMMAND_CATEGORY["channelAspirate"] == EventCategory.ASPIRATE
    assert COMMAND_CATEGORY["channelDispense"] == EventCategory.DISPENSE
    assert COMMAND_CATEGORY["channelTipEject"] == EventCategory.TIP_EJECT
    assert COMMAND_CATEGORY["mph96TipPickUp"] == EventCategory.TIP_PICKUP
    assert COMMAND_CATEGORY["mph96Aspirate"] == EventCategory.ASPIRATE
    assert COMMAND_CATEGORY["mph96Dispense"] == EventCategory.DISPENSE
    assert COMMAND_CATEGORY["mph96TipEject"] == EventCategory.TIP_EJECT
    assert COMMAND_CATEGORY["ODTC_GetStatus"] == EventCategory.OTHER
    assert COMMAND_CATEGORY["end"] == EventCategory.OTHER


def test_odtc_commands_in_robot_json(tmp_path):
    path = write_log(
        tmp_path,
        [
            "{'command': 'ODTC_Connect', 'id': '0x1'}",
            "{'command': 'ODTC_ExecuteMethod', 'id': '0x2', 'MethodName': 'PCR'}",
            "{'command': 'ODTC_OpenDoor', 'id': '0x3'}",
            "{'command': 'ODTC_CloseDoor', 'id': '0x4'}",
            "{'command': 'ODTC_Reset', 'id': '0x5'}",
        ],
    )

    events = parse_robot_json_log(path)

    assert [event.category for event in events] == [EventCategory.MODULE_ACTION] * 5
    assert [event.action for event in events] == [
        "connect",
        "run_program",
        "open_door",
        "close_door",
        "reset",
    ]
    assert all(event.resources == ["ODTC"] for event in events)


def test_transport_pairing(tmp_path):
    path = write_log(
        tmp_path,
        [
            "{'command': 'gripGet', 'id': '0x1', 'labwarePositions': 'Source Plate, 1'}",
            "{'command': 'gripPlace', 'id': '0x2', 'labwarePositions': 'Destination Nest, 1'}",
            "{'command': 'iSwapGet', 'id': '0x3', 'labwarePositions': 'Lid A, 1'}",
            "{'command': 'iSwapPlace', 'id': '0x4', 'labwarePositions': 'Lid B, 1'}",
        ],
    )

    events = parse_robot_json_log(path)

    assert len(events) == 2
    assert all(event.category == EventCategory.TRANSPORT for event in events)
    assert events[0].resources == ["Source Plate", "Destination Nest"]
    assert events[1].resources == ["Lid A", "Lid B"]


def test_channel_count_from_channel_variable(tmp_path):
    path = write_log(
        tmp_path,
        [
            "{'command': 'channelDispense', 'id': '0x1', 'channelVariable': '1111111100000000'}",
        ],
    )

    events = parse_robot_json_log(path)

    assert events[0].channel_count == 8


def test_parse_existing_robot_json_fixture():
    fixture = Path("pyhamilton/ngs/tests/log/robot_json.log")

    events = parse_robot_json_log(fixture)

    histogram = {}
    for event in events:
        histogram[event.category] = histogram.get(event.category, 0) + 1

    assert len(events) == 1693
    assert histogram[EventCategory.ASPIRATE] == 572
    assert histogram[EventCategory.TIP_PICKUP] == 359
    assert histogram[EventCategory.DISPENSE] == 350
    assert histogram[EventCategory.TIP_EJECT] == 349
    assert histogram[EventCategory.OTHER] == 63
