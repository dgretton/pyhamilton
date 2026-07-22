import pytest

from pyhamilton.verification.method_tree import (
    LOOP_BODY_MULTIPLIER,
    LOOP_FULLY_UNROLLED,
    LOOP_NONE,
    detect_loop_convention,
    expand_method_tree,
    stepcard_to_normalized_event,
)
from pyhamilton.verification.models import EventCategory


def test_loop_convention_detection():
    steps = [{"action": "initialize"}] * 6

    assert (
        detect_loop_convention(
            steps,
            [{"start_step": 1, "end_step": 2, "iterations": 3, "iteration_size": 2}],
        )
        == LOOP_BODY_MULTIPLIER
    )
    assert (
        detect_loop_convention(
            steps,
            [{"start_step": 1, "end_step": 6, "iterations": 3, "iteration_size": 2}],
        )
        == LOOP_FULLY_UNROLLED
    )
    assert detect_loop_convention(steps, []) == LOOP_NONE


def test_loop_expansion_body_multiplier():
    steps = [
        {"action": "initialize"},
        {"action": "aspirate", "params": {"source": "Plate", "volume_ul": 10}},
        {"action": "dispense", "params": {"destination": "Plate", "volume_ul": 10}},
        {"action": "wait"},
    ]
    loop_groups = [{"start_step": 2, "end_step": 3, "iterations": 3, "iteration_size": 2}]

    events = expand_method_tree(steps, loop_groups)

    assert [event.category for event in events] == [
        EventCategory.INITIALIZE,
        EventCategory.ASPIRATE,
        EventCategory.DISPENSE,
        EventCategory.ASPIRATE,
        EventCategory.DISPENSE,
        EventCategory.ASPIRATE,
        EventCategory.DISPENSE,
        EventCategory.WAIT,
    ]
    assert [event.sequence for event in events] == list(range(8))


def test_loop_expansion_fully_unrolled():
    steps = [
        {"action": "aspirate", "params": {"source": "Plate"}},
        {"action": "dispense", "params": {"destination": "Plate"}},
        {"action": "aspirate", "params": {"source": "Plate"}},
        {"action": "dispense", "params": {"destination": "Plate"}},
    ]
    loop_groups = [{"start_step": 1, "end_step": 4, "iterations": 2, "iteration_size": 2}]

    events = expand_method_tree(steps, loop_groups)

    assert [event.category for event in events] == [
        EventCategory.ASPIRATE,
        EventCategory.DISPENSE,
        EventCategory.ASPIRATE,
        EventCategory.DISPENSE,
    ]


@pytest.mark.parametrize(
    ("card", "category", "resources", "volume", "head"),
    [
        ({"action": "initialize", "params": {"targets": ["Deck"]}}, EventCategory.INITIALIZE, ["Deck"], None, None),
        ({"action": "transport", "params": {"from": "A", "to": "B"}}, EventCategory.TRANSPORT, ["A", "B"], None, None),
        ({"action": "lid_transport", "params": {"from": "A", "to": "B"}}, EventCategory.LID_TRANSPORT, ["A", "B"], None, None),
        ({"action": "module_action", "params": {"target": "ODTC", "action": "open_door"}}, EventCategory.MODULE_ACTION, ["ODTC"], None, None),
        ({"action": "tip_pickup", "params": {"tip_source": "Tips", "head": "head_8ch"}}, EventCategory.TIP_PICKUP, ["Tips"], None, "head_8ch"),
        ({"action": "tip_eject", "params": {"destination": "Waste", "head": "head_8ch"}}, EventCategory.TIP_EJECT, ["Waste"], None, "head_8ch"),
        ({"action": "tip_pickup_8ch", "params": {"from": "Tips"}}, EventCategory.TIP_PICKUP, ["Tips"], None, "head_8ch"),
        ({"action": "tip_eject_8ch", "params": {"to": "Waste"}}, EventCategory.TIP_EJECT, ["Waste"], None, "head_8ch"),
        ({"action": "tip_pickup_96mph", "params": {"from": "Tips96"}}, EventCategory.TIP_PICKUP, ["Tips96"], None, "head_96mph"),
        ({"action": "tip_eject_96mph", "params": {"to": "Waste"}}, EventCategory.TIP_EJECT, ["Waste"], None, "head_96mph"),
        ({"action": "tip_transfer_to_adapter", "params": {"from": "Rack", "to": "Adapter"}}, EventCategory.TIP_STAGING, ["Rack", "Adapter"], None, "head_96mph"),
        ({"action": "tip_return_to_rack", "params": {"to": "Rack", "actor": "head_96mph"}}, EventCategory.TIP_STAGING, ["Rack"], None, "head_96mph"),
        ({"action": "aspirate", "params": {"source": "Source", "volume_ul": 20, "head": "head_8ch"}}, EventCategory.ASPIRATE, ["Source"], 20.0, "head_8ch"),
        ({"action": "dispense", "params": {"destination": "Dest", "volume_ul": 20, "head": "head_8ch"}}, EventCategory.DISPENSE, ["Dest"], 20.0, "head_8ch"),
        ({"action": "pipette_dwell", "params": {"operation": "mix", "at": "Plate", "volume_ul": 30, "actor": "head_8ch"}}, EventCategory.MIX, ["Plate"], 30.0, "head_8ch"),
        ({"action": "incubate"}, EventCategory.WAIT, [], None, None),
        ({"action": "wait"}, EventCategory.WAIT, [], None, None),
    ],
)
def test_stepcard_to_normalized_event(card, category, resources, volume, head):
    event = stepcard_to_normalized_event(card)

    assert event.category == category
    assert event.resources == resources
    assert event.volume_ul == volume
    assert event.head == head


def test_pipette_dwell_operation_mapping_and_implicit_column_channels():
    event = stepcard_to_normalized_event(
        {
            "action": "pipette_dwell",
            "params": {
                "operation": "aspirate",
                "at": "Plate",
                "volume_ul": 5,
                "actor": "head_8ch",
                "at_column": 3,
            },
        }
    )

    assert event.category == EventCategory.ASPIRATE
    assert event.channel_count == 8
