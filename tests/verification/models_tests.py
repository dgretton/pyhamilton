from pyhamilton.verification.models import (
    EventCategory,
    NormalizedEvent,
    normalize_resource_name,
    parse_labware_positions,
)


def test_event_category_has_spec_values():
    assert {category.value for category in EventCategory} == {
        "initialize",
        "tip_pickup",
        "tip_eject",
        "aspirate",
        "dispense",
        "mix",
        "transport",
        "lid_transport",
        "module_action",
        "wait",
        "tip_staging",
        "other",
    }


def test_normalized_event_defaults():
    event = NormalizedEvent(
        sequence=0,
        category=EventCategory.INITIALIZE,
        action="initialize",
    )

    assert event.resources == []
    assert event.volume_ul is None
    assert event.head is None
    assert event.channel_count is None
    assert event.metadata == {}


def test_resource_name_normalization_preserves_case_and_collapses_whitespace():
    assert normalize_resource_name("  Plate   A\t1\n") == "Plate A 1"
    assert normalize_resource_name("plate a 1") == "plate a 1"


def test_parse_labware_positions_extracts_resource_names_and_dedupes():
    field = " Plate   A, 1;Plate A, 2; Tips 300uL, 4; ;Plate A, 3 "

    assert parse_labware_positions(field) == ["Plate A", "Tips 300uL"]


def test_parse_labware_positions_handles_empty_values():
    assert parse_labware_positions("") == []
    assert parse_labware_positions(None) == []
