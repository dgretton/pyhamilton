from pyhamilton.verification.checks import (
    FAIL,
    PASS,
    WARN,
    category_histogram,
    check_a_health_01,
    check_a_health_02,
    check_a_health_03,
    run_tier_a_checks,
)
from pyhamilton.verification.models import EventCategory, NormalizedEvent, RunHealthReport


def event(category, resources=None, action=None):
    return NormalizedEvent(
        sequence=0,
        category=category,
        action=action or category.value,
        resources=resources or [],
    )


def result_by_id(results):
    return {result.id: result for result in results}


def test_category_histogram():
    hist = category_histogram(
        [
            event(EventCategory.ASPIRATE),
            event(EventCategory.ASPIRATE),
            event(EventCategory.OTHER),
            event(EventCategory.DISPENSE),
        ]
    )

    assert hist[EventCategory.ASPIRATE] == 2
    assert hist[EventCategory.DISPENSE] == 1
    assert EventCategory.OTHER not in hist


def test_health_checks():
    failed_analysis = RunHealthReport(
        guid="g",
        analyzed_ok=False,
        connected=True,
        reached_end=False,
        errors=["Analyze method - error"],
    )
    hung_run = RunHealthReport(
        guid="g",
        analyzed_ok=True,
        connected=True,
        reached_end=False,
    )

    assert check_a_health_01(failed_analysis).verdict == FAIL
    assert check_a_health_02(hung_run).verdict == FAIL
    assert check_a_health_03(failed_analysis).verdict == WARN


def test_tier_a_struct_01_empty_tree_rich_sim():
    results = result_by_id(
        run_tier_a_checks(
            [event(EventCategory.INITIALIZE, ["Deck"])],
            [
                event(EventCategory.INITIALIZE, ["Deck"]),
                event(EventCategory.ASPIRATE, ["Plate"]),
            ],
        )
    )

    assert results["A-STRUCT-01"].verdict == FAIL


def test_tier_a_struct_02_rich_tree_empty_sim():
    results = result_by_id(
        run_tier_a_checks(
            [
                event(EventCategory.INITIALIZE, ["Deck"]),
                event(EventCategory.ASPIRATE, ["Plate"]),
            ],
            [event(EventCategory.INITIALIZE, ["Deck"])],
        )
    )

    assert results["A-STRUCT-02"].verdict == FAIL


def test_tier_a_struct_03_histogram_match():
    events = [
        event(EventCategory.INITIALIZE, ["Deck"]),
        event(EventCategory.ASPIRATE, ["Plate"]),
        event(EventCategory.DISPENSE, ["Plate"]),
    ]

    assert run_tier_a_checks(events, events) == []


def test_tier_a_struct_03_histogram_divergence():
    results = result_by_id(
        run_tier_a_checks(
            [
                event(EventCategory.ASPIRATE, ["Plate"]),
                event(EventCategory.ASPIRATE, ["Plate"]),
                event(EventCategory.ASPIRATE, ["Plate"]),
            ],
            [event(EventCategory.ASPIRATE, ["Plate"])],
        )
    )

    assert results["A-STRUCT-03"].verdict == WARN


def test_tier_a_struct_04_missing_category():
    results = result_by_id(
        run_tier_a_checks(
            [event(EventCategory.ASPIRATE, ["Plate"])],
            [event(EventCategory.DISPENSE, ["Plate"])],
        )
    )

    assert results["A-STRUCT-04"].verdict == WARN


def test_tier_a_resource_warnings():
    results = result_by_id(
        run_tier_a_checks(
            [event(EventCategory.ASPIRATE, ["Tree Plate"])],
            [event(EventCategory.ASPIRATE, ["Sim Plate"])],
        )
    )

    assert results["A-RES-01"].verdict == WARN
    assert results["A-RES-02"].verdict == WARN


def test_tier_a_odtc_01_odtc_in_tree_not_sim():
    results = result_by_id(
        run_tier_a_checks(
            [event(EventCategory.MODULE_ACTION, ["ODTC"])],
            [event(EventCategory.MODULE_ACTION, ["HHS"])],
        )
    )

    assert results["A-ODTC-01"].verdict == WARN


def test_tier_a_odtc_02_odtc_in_sim_not_tree():
    results = result_by_id(
        run_tier_a_checks(
            [event(EventCategory.MODULE_ACTION, ["HHS"])],
            [event(EventCategory.MODULE_ACTION, ["ODTC"])],
        )
    )

    assert results["A-ODTC-02"].verdict == WARN


def test_tier_a_all_pass_clean_run():
    method_tree_events = [
        event(EventCategory.INITIALIZE, ["Deck"]),
        event(EventCategory.TIP_PICKUP, ["Tips"]),
        event(EventCategory.ASPIRATE, ["Plate"]),
        event(EventCategory.DISPENSE, ["Plate"]),
        event(EventCategory.TIP_EJECT, ["Waste"]),
    ]
    sim_events = [
        event(EventCategory.INITIALIZE, ["Deck"]),
        event(EventCategory.TIP_PICKUP, ["Tips"]),
        event(EventCategory.ASPIRATE, ["Plate"]),
        event(EventCategory.DISPENSE, ["Plate"]),
        event(EventCategory.TIP_EJECT, ["Waste"]),
    ]
    health = RunHealthReport(
        guid="g",
        analyzed_ok=True,
        connected=True,
        reached_end=True,
    )

    assert run_tier_a_checks(method_tree_events, sim_events, health) == []


def test_script_checks_warn_by_default_constraint():
    results = result_by_id(
        run_tier_a_checks([], [], script_raised_exception=True, fake_runtime_rejected=True)
    )

    assert results["A-SCRIPT-01"].verdict == WARN
    assert results["A-SCRIPT-02"].verdict == WARN


def test_passing_health_check_result_is_pass():
    health = RunHealthReport(guid="g", analyzed_ok=True, connected=True, reached_end=True)

    assert check_a_health_01(health).verdict == PASS
