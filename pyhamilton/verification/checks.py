"""Tier A deterministic verification checks."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from pyhamilton.verification.models import EventCategory, NormalizedEvent, RunHealthReport


PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

COMPARABLE_CATEGORIES = {
    category for category in EventCategory if category != EventCategory.OTHER
}
RICH_CATEGORIES = {
    EventCategory.TIP_PICKUP,
    EventCategory.TIP_EJECT,
    EventCategory.ASPIRATE,
    EventCategory.DISPENSE,
    EventCategory.MIX,
    EventCategory.TRANSPORT,
    EventCategory.LID_TRANSPORT,
    EventCategory.MODULE_ACTION,
    EventCategory.TIP_STAGING,
}


@dataclass
class CheckResult:
    id: str
    verdict: str
    message: str


def category_histogram(events: Iterable[NormalizedEvent]) -> Counter[EventCategory]:
    return Counter(
        event.category
        for event in events
        if event.category in COMPARABLE_CATEGORIES
    )


def check_a_health_01(health_report: RunHealthReport | None) -> CheckResult:
    if health_report is None or health_report.analyzed_ok:
        return CheckResult("A-HEALTH-01", PASS, "Method analyzed successfully")
    return CheckResult("A-HEALTH-01", FAIL, "Method did not analyze successfully")


def check_a_health_02(health_report: RunHealthReport | None) -> CheckResult:
    if health_report is None:
        return CheckResult("A-HEALTH-02", PASS, "No trace health report provided")
    if health_report.reached_end or not health_report.analyzed_ok:
        return CheckResult("A-HEALTH-02", PASS, "Run reached end or analysis failed first")
    return CheckResult("A-HEALTH-02", FAIL, "Run analyzed successfully but did not reach end")


def check_a_health_03(health_report: RunHealthReport | None) -> CheckResult:
    if health_report is None or not health_report.errors:
        return CheckResult("A-HEALTH-03", PASS, "No trace errors found")
    return CheckResult("A-HEALTH-03", WARN, f"Trace contains {len(health_report.errors)} error line(s)")


def check_a_struct_01(
    method_tree_events: list[NormalizedEvent],
    sim_events: list[NormalizedEvent],
) -> CheckResult:
    if _is_initialize_only(method_tree_events) and _has_rich_events(sim_events):
        return CheckResult(
            "A-STRUCT-01",
            FAIL,
            "Method tree is initialize-only but simulation contains rich protocol events",
        )
    return CheckResult("A-STRUCT-01", PASS, "No empty-tree/rich-simulation mismatch")


def check_a_struct_02(
    method_tree_events: list[NormalizedEvent],
    sim_events: list[NormalizedEvent],
) -> CheckResult:
    if _has_rich_events(method_tree_events) and _is_initialize_only(sim_events):
        return CheckResult(
            "A-STRUCT-02",
            FAIL,
            "Method tree contains rich protocol events but simulation is empty or initialize-only",
        )
    return CheckResult("A-STRUCT-02", PASS, "No rich-tree/empty-simulation mismatch")


def check_a_struct_03(
    method_tree_events: list[NormalizedEvent],
    sim_events: list[NormalizedEvent],
) -> CheckResult:
    tree_hist = category_histogram(method_tree_events)
    sim_hist = category_histogram(sim_events)
    divergent: list[str] = []
    for category in sorted(set(tree_hist) & set(sim_hist), key=lambda item: item.value):
        tree_count = tree_hist[category]
        sim_count = sim_hist[category]
        if max(tree_count, sim_count) and abs(tree_count - sim_count) / max(tree_count, sim_count) > 0.5:
            divergent.append(f"{category.value}: tree={tree_count}, sim={sim_count}")

    if divergent:
        return CheckResult(
            "A-STRUCT-03",
            WARN,
            "Category histogram divergence >50%: " + "; ".join(divergent),
        )
    return CheckResult("A-STRUCT-03", PASS, "Category histograms are within threshold")


def check_a_struct_04(
    method_tree_events: list[NormalizedEvent],
    sim_events: list[NormalizedEvent],
) -> CheckResult:
    tree_categories = set(category_histogram(method_tree_events))
    sim_categories = set(category_histogram(sim_events))
    missing_from_sim = sorted(tree_categories - sim_categories, key=lambda item: item.value)
    missing_from_tree = sorted(sim_categories - tree_categories, key=lambda item: item.value)

    if missing_from_sim or missing_from_tree:
        details = []
        if missing_from_sim:
            details.append("tree-only: " + ", ".join(category.value for category in missing_from_sim))
        if missing_from_tree:
            details.append("simulation-only: " + ", ".join(category.value for category in missing_from_tree))
        return CheckResult("A-STRUCT-04", WARN, "Missing category: " + "; ".join(details))
    return CheckResult("A-STRUCT-04", PASS, "No missing categories")


def check_a_res_01(
    method_tree_events: list[NormalizedEvent],
    sim_events: list[NormalizedEvent],
) -> CheckResult:
    sim_only = sorted(_resources(sim_events) - _resources(method_tree_events))
    if sim_only:
        return CheckResult("A-RES-01", WARN, "Simulation-only resources: " + ", ".join(sim_only))
    return CheckResult("A-RES-01", PASS, "No simulation-only resources")


def check_a_res_02(
    method_tree_events: list[NormalizedEvent],
    sim_events: list[NormalizedEvent],
) -> CheckResult:
    tree_only = sorted(_resources(method_tree_events) - _resources(sim_events))
    if tree_only:
        return CheckResult("A-RES-02", WARN, "Tree-only resources: " + ", ".join(tree_only))
    return CheckResult("A-RES-02", PASS, "No tree-only resources")


def check_a_odtc_01(
    method_tree_events: list[NormalizedEvent],
    sim_events: list[NormalizedEvent],
) -> CheckResult:
    if _has_odtc_module_action(method_tree_events) and not _has_odtc_module_action(sim_events):
        return CheckResult("A-ODTC-01", WARN, "ODTC module action appears in tree but not simulation")
    return CheckResult("A-ODTC-01", PASS, "No tree-only ODTC module action")


def check_a_odtc_02(
    method_tree_events: list[NormalizedEvent],
    sim_events: list[NormalizedEvent],
) -> CheckResult:
    if _has_odtc_module_action(sim_events) and not _has_odtc_module_action(method_tree_events):
        return CheckResult("A-ODTC-02", WARN, "ODTC module action appears in simulation but not tree")
    return CheckResult("A-ODTC-02", PASS, "No simulation-only ODTC module action")


def check_a_script_01(script_raised_exception: bool = False) -> CheckResult:
    if script_raised_exception:
        return CheckResult("A-SCRIPT-01", WARN, "Script raised an exception")
    return CheckResult("A-SCRIPT-01", PASS, "Script did not raise an exception")


def check_a_script_02(fake_runtime_rejected: bool = False) -> CheckResult:
    if fake_runtime_rejected:
        return CheckResult("A-SCRIPT-02", WARN, "Fake-runtime tracer rejected script")
    return CheckResult("A-SCRIPT-02", PASS, "Fake-runtime tracer did not reject script")


def run_tier_a_checks(
    method_tree_events: list[NormalizedEvent],
    sim_events: list[NormalizedEvent],
    health_report: RunHealthReport | None = None,
    *,
    script_raised_exception: bool = False,
    fake_runtime_rejected: bool = False,
) -> list[CheckResult]:
    checks = [
        check_a_health_01(health_report),
        check_a_health_02(health_report),
        check_a_health_03(health_report),
        check_a_struct_01(method_tree_events, sim_events),
        check_a_struct_02(method_tree_events, sim_events),
        check_a_struct_03(method_tree_events, sim_events),
        check_a_struct_04(method_tree_events, sim_events),
        check_a_res_01(method_tree_events, sim_events),
        check_a_res_02(method_tree_events, sim_events),
        check_a_odtc_01(method_tree_events, sim_events),
        check_a_odtc_02(method_tree_events, sim_events),
        check_a_script_01(script_raised_exception),
        check_a_script_02(fake_runtime_rejected),
    ]
    return [check for check in checks if check.verdict != PASS]


def _is_initialize_only(events: list[NormalizedEvent]) -> bool:
    categories = {event.category for event in events if event.category != EventCategory.OTHER}
    return not categories or categories <= {EventCategory.INITIALIZE}


def _has_rich_events(events: list[NormalizedEvent]) -> bool:
    return any(event.category in RICH_CATEGORIES for event in events)


def _resources(events: Iterable[NormalizedEvent]) -> set[str]:
    return {
        resource
        for event in events
        if event.category != EventCategory.OTHER
        for resource in event.resources
    }


def _has_odtc_module_action(events: Iterable[NormalizedEvent]) -> bool:
    for event in events:
        if event.category != EventCategory.MODULE_ACTION:
            continue
        resources = {resource.lower() for resource in event.resources}
        target = str(event.metadata.get("target") or "").lower()
        card = event.metadata.get("card")
        if isinstance(card, dict):
            params = card.get("params") or {}
            if isinstance(params, dict):
                target = str(params.get("target") or target).lower()
        if "odtc" in resources or target == "odtc":
            return True
    return False

