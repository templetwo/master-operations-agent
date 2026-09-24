"""Dependency-scoped, deterministic policy for the new synthetic stream path.

Inputs are already validated operator rows and public configuration. ``grid``
contains the 25 aligned five-second samples at or before the current sample;
missing slots are None. Current bad quality invalidates cached dependent trends
immediately. Integer milli-values preserve the legacy numerical thresholds, not
the legacy floating-point representation or global history-quality behavior.

Unusable current points are reported in a separate ``unusable_measurements``
array so a fixed finding name can carry a validated tag and a fixed reason/text.
The ordinary findings list remains catalog IDs. Neither array supplies authority.
"""

from copy import deepcopy
from decimal import Decimal

from .knowledge import CHECKS as LEGACY_CHECKS, FINDINGS as LEGACY_FINDINGS

POLICY_ID = "lab-v2-deps"
TAGS = ("FI100", "LIC101", "FIC102", "TIC201", "TIC202")
TREND_TAGS = ("TIC201", "TIC202", "FIC102", "LIC101")
CHANGE_FINDINGS = ("reactor_warming", "reactor_cooling", "reactor_below_window_peak",
                   "jacket_warming", "feed_flow_increased", "tank_level_increased")
NUMERICAL_FINDINGS = (*CHANGE_FINDINGS, "coolant_output_high", "cooling_path_unconfirmed",
                      "no_large_net_change", "cause_unresolved")
DEPENDENCIES = {
    "reported_alarms": {"kind": "instant_alarm", "requires_complete_coverage": True},
    "no_reported_alarms": {"kind": "instant_alarm", "requires_complete_coverage": True},
    "reactor_warming": {"kind": "window", "tags": ["TIC201"]},
    "reactor_cooling": {"kind": "window", "tags": ["TIC201"]},
    "reactor_below_window_peak": {"kind": "window", "tags": ["TIC201"]},
    "jacket_warming": {"kind": "window", "tags": ["TIC202"]},
    "feed_flow_increased": {"kind": "window", "tags": ["FIC102"]},
    "tank_level_increased": {"kind": "window", "tags": ["LIC101"]},
    "coolant_output_high": {"kind": "instant_output", "tag": "TIC202", "field": "op_milli"},
    "cooling_path_unconfirmed": {"kind": "conjunction", "findings": [
        "reactor_warming", "jacket_warming", "coolant_output_high"]},
    "no_large_net_change": {"kind": "window", "tags": list(TREND_TAGS)},
    "cause_unresolved": {"kind": "supported_change", "any_findings": list(CHANGE_FINDINGS)},
}
FINDINGS = {name: LEGACY_FINDINGS[name] for name in DEPENDENCIES}
CHECKS = deepcopy(LEGACY_CHECKS)
UNUSABLE_TEXT = {
    "source_quality_bad": "The source marks this measurement unusable. Findings that require its value are withheld.",
    "missing_value": "This measurement has no usable integer milli-value. Findings that require its value are withheld.",
    "missing_point": "This required measurement is absent. Findings that require its value are withheld.",
}
POLICY = {
    "id": POLICY_ID,
    "profile": "ess-u1-stream-v1",
    "findings": FINDINGS,
    "checks": CHECKS,
    "dependencies": DEPENDENCIES,
    "history": {"samples": 25, "cadence_s": 5, "span_s": 120,
                "requirement": "All 25 slots must have GOOD integer values for each required tag. Current unusable quality immediately invalidates that tag's cached window."},
    "thresholds_milli": {"reactor_net": 2000, "jacket_net": 3000,
                         "feed_net": 5000, "level_net": 3000, "coolant_output": 95000},
    "rules": {
        "reactor_warming": "last TIC201 - first TIC201 >= 2000",
        "reactor_cooling": "last TIC201 - first TIC201 <= -2000",
        "reactor_below_window_peak": "max TIC201 - first TIC201 >= 2000 AND max TIC201 - last TIC201 >= 2000",
        "jacket_warming": "last TIC202 - first TIC202 >= 3000",
        "feed_flow_increased": "last FIC102 - first FIC102 >= 5000",
        "tank_level_increased": "last LIC101 - first LIC101 >= 3000",
        "coolant_output_high": "Current TIC202 op_milli >= 95000; PV source_quality does not describe the output indication.",
        "cooling_path_unconfirmed": "All three dependency findings are supported.",
        "no_large_net_change": "Absolute net changes TIC201 < 2000, TIC202 < 3000, FIC102 < 5000, LIC101 < 3000. This is not proof of safety.",
        "cause_unresolved": "Include only when at least one supported temporal-change finding applies, never for quiet data or high output alone.",
        "over_range": "Compare current GOOD PV milli-value with its own configured lo/hi times 1000. This is a separate flag, not fabricated source quality or a new physics test.",
    },
    "unusable_measurements": {"finding": "unusable_measurement", "reason_text": UNUSABLE_TEXT},
    "check_rules": {
        "compare_independent_measurement": "Always include this review check; it is not a claim that confirmation occurred.",
        "inspect_alarm_context": "Include when complete coverage supports reported_alarms.",
        "continue_observation": "Include when complete coverage supports no_reported_alarms.",
        "review_cooling_evidence": "Include for supported cooling_path_unconfirmed.",
        "review_feed_balance": "Include for supported feed_flow_increased or tank_level_increased.",
        "monitor_thermal_recovery": "Include for supported reactor_cooling or reactor_below_window_peak.",
        "capture_clean_window": "Include for missing history slots, unusable current measurements, unusable dependent historical measurements, or an active global-quality gate.",
    },
    "outcome_rules": {
        "observation_incomplete": "Current unusable measurement, unusable required historical measurement, incomplete alarm coverage, or global quality gate. Unrelated supported findings are retained only in scoped mode.",
        "advisory": "Otherwise, an active alarm, supported temporal change, or high current coolant output requires attention.",
        "normal_within_scope": "Otherwise, no_large_net_change is supported, no finding is withheld, no current point is over range, and no alarm is active. This is a bounded observation, not a safety claim.",
        "no_finding_supported": "Remaining cases, including startup without a supported instantaneous attention finding.",
    },
    "degradation": "By default, withhold only dependent findings. Disabling scoped degradation withholds all findings, including alarm IDs, on any unusable current or historical measurement. Structural unusable-measurement notices remain visible.",
    "outcomes": ["advisory", "observation_incomplete", "no_finding_supported", "normal_within_scope"],
    "provenance": "Project-authored synthetic research policy. No controls-engineer approval, new physics, unique-cause claim, or operational authority.",
}


def read_policy():
    """Return a detached catalog suitable for a read-only tool response."""
    return deepcopy(POLICY)


def _points(row):
    return {point["tag"]: point for point in row["points"]} if row is not None else {}


def _unusable_reason(point):
    if point is None:
        return "missing_point"
    if point["source_quality"] != "GOOD":
        return "source_quality_bad"
    if type(point["value_milli"]) is not int:
        return "missing_value"
    return None


def assess(sample, grid, config, *, scoped_degradation=True):
    """Select fixed policy IDs from validated evidence without side effects.

    Missing startup slots withhold trends but do not suppress instantaneous
    alarm/output assessment. Over-range GOOD data stays available for numerical
    assessment; the separate range flag prevents a normal-within-scope outcome.
    """
    if type(scoped_degradation) is not bool:
        raise ValueError("scoped_degradation must be boolean.")
    points = _points(sample)
    history = [_points(row) for row in grid]
    findings, checks, withheld, notices = [], [], [], []
    unavailable = {}

    def add_check(name):
        if name not in checks:
            checks.append(name)

    def withhold(name, reason):
        unavailable[name] = reason
        withheld.append({"finding": name, "reason": reason})

    derived = {}
    for tag in TAGS:
        point = points.get(tag)
        reason = _unusable_reason(point)
        if reason:
            notices.append({"finding": "unusable_measurement", "tag": tag,
                            "reason": reason, "text": UNUSABLE_TEXT[reason]})
        bounds = config["tags"][tag]
        value = point["value_milli"] if point is not None and reason is None else None
        over_range = value is not None and (
            (bounds["lo"] is not None and Decimal(value) < Decimal(str(bounds["lo"])) * 1000)
            or (bounds["hi"] is not None and Decimal(value) > Decimal(str(bounds["hi"])) * 1000))
        derived[tag] = {"over_range": bool(over_range)}

    historical_unusable = any(_unusable_reason(row.get(tag)) is not None
                              for row in history if row for tag in TREND_TAGS)
    historical_any_unusable = any(_unusable_reason(row.get(tag)) is not None
                                  for row in history if row for tag in TAGS)
    global_gate = not scoped_degradation and (bool(notices) or historical_any_unusable)
    complete_alarms = sample["alarms_omitted"] == 0 and sample["alarms_total_matched"] == len(sample["alarms"])
    if global_gate:
        withhold("reported_alarms", "global_quality_gate")
        withhold("no_reported_alarms", "global_quality_gate")
    elif complete_alarms:
        if sample["alarms"]:
            findings.append("reported_alarms")
            add_check("inspect_alarm_context")
            add_check("compare_independent_measurement")
        else:
            findings.append("no_reported_alarms")
            add_check("continue_observation")
    else:
        withhold("reported_alarms", "incomplete_alarm_coverage")
        withhold("no_reported_alarms", "incomplete_alarm_coverage")

    windows, window_reasons = {}, {}
    for tag in TREND_TAGS:
        if global_gate:
            window_reasons[tag] = "global_quality_gate"
        elif _unusable_reason(points.get(tag)) is not None:
            window_reasons[tag] = "current_measurement_unusable"
        elif len(grid) != 25 or any(row is None for row in grid):
            window_reasons[tag] = "incomplete_history"
        elif any(_unusable_reason(row.get(tag)) is not None for row in history):
            window_reasons[tag] = "historical_measurement_unusable"
        else:
            windows[tag] = [row[tag]["value_milli"] for row in history]

    deltas = {tag: values[-1] - values[0] for tag, values in windows.items()}
    rules = (
        ("reactor_warming", "TIC201", lambda values: values[-1] - values[0] >= 2000),
        ("reactor_cooling", "TIC201", lambda values: values[-1] - values[0] <= -2000),
        ("reactor_below_window_peak", "TIC201", lambda values: max(values) - values[0] >= 2000 and max(values) - values[-1] >= 2000),
        ("jacket_warming", "TIC202", lambda values: values[-1] - values[0] >= 3000),
        ("feed_flow_increased", "FIC102", lambda values: values[-1] - values[0] >= 5000),
        ("tank_level_increased", "LIC101", lambda values: values[-1] - values[0] >= 3000),
    )
    for finding, tag, applies in rules:
        if tag in window_reasons:
            withhold(finding, window_reasons[tag])
        elif applies(windows[tag]):
            findings.append(finding)

    output = points.get("TIC202", {}).get("op_milli")
    if global_gate:
        withhold("coolant_output_high", "global_quality_gate")
    elif type(output) is not int:
        withhold("coolant_output_high", "output_unavailable")
    elif output >= 95000:
        findings.append("coolant_output_high")

    cooling_dependencies = DEPENDENCIES["cooling_path_unconfirmed"]["findings"]
    if any(name in unavailable for name in cooling_dependencies):
        withhold("cooling_path_unconfirmed", "global_quality_gate" if global_gate else "dependency_unavailable")
    elif all(name in findings for name in cooling_dependencies):
        findings.append("cooling_path_unconfirmed")

    if window_reasons:
        reason = "global_quality_gate" if global_gate else "dependency_unavailable"
        withhold("no_large_net_change", reason)
    elif all(abs(deltas[tag]) < threshold for tag, threshold in
             (("TIC201", 2000), ("TIC202", 3000), ("FIC102", 5000), ("LIC101", 3000))):
        findings.append("no_large_net_change")

    if any(name in findings for name in CHANGE_FINDINGS):
        findings.append("cause_unresolved")
    elif any(name in unavailable for name in CHANGE_FINDINGS):
        withhold("cause_unresolved", "global_quality_gate" if global_gate else "dependency_unavailable")

    add_check("compare_independent_measurement")
    if "cooling_path_unconfirmed" in findings:
        add_check("review_cooling_evidence")
    if {"feed_flow_increased", "tank_level_increased"}.intersection(findings):
        add_check("review_feed_balance")
    if {"reactor_cooling", "reactor_below_window_peak"}.intersection(findings):
        add_check("monitor_thermal_recovery")
    if notices or historical_unusable or global_gate or any(row is None for row in grid) or len(grid) != 25:
        add_check("capture_clean_window")

    active_alarm = any(alarm["active"] for alarm in sample["alarms"])
    numerical_attention = set(findings).intersection(NUMERICAL_FINDINGS) - {"no_large_net_change"}
    if notices or historical_unusable or global_gate or not complete_alarms:
        outcome = "observation_incomplete"
    elif active_alarm or numerical_attention:
        outcome = "advisory"
    elif ("no_large_net_change" in findings and not withheld
          and not any(value["over_range"] for value in derived.values())):
        outcome = "normal_within_scope"
    else:
        outcome = "no_finding_supported"
    return {"outcome": outcome, "findings": findings, "checks": checks, "withheld": withheld,
            "derived": derived, "unusable_measurements": notices}
