"""Project-authored research policy. Controls-engineer review is still pending."""

from .contracts import digest

CHECKS = {
    "inspect_alarm_context": "Review the reported alarm conditions and their operator procedure in the simulator.",
    "compare_independent_measurement": "Compare an independent simulator indication before accepting a causal explanation.",
    "review_cooling_evidence": "Inspect the simulator cooling indications and trend history. The two values do not establish a root cause.",
    "continue_observation": "Continue observing the simulator. An empty alarm list does not establish a safe process.",
    "review_feed_balance": "Compare simulator feed and tank-level trends before attributing the disturbance to a feed change.",
    "monitor_thermal_recovery": "Continue observing reactor and jacket trends. Falling temperature alone does not prove recovery or authorize restoring a control setting.",
    "capture_clean_window": "Obtain a complete window of reliable indications before drawing a trend-based conclusion.",
}
FINDINGS = {
    "reported_alarms": "The snapshot reports alarm records. Their presence alone does not establish the initiating cause.",
    "no_reported_alarms": "The snapshot reports no alarms within its declared coverage.",
    "cooling_mismatch": "The demo temperature is above 80 degC while demo coolant flow is below 20 L/min. Possible cooling impairment needs independent confirmation.",
    "reactor_warming": "Reactor temperature increased by at least 2 DEG C from the first to the last sample in the simulation window.",
    "reactor_cooling": "Reactor temperature decreased by at least 2 DEG C across the simulation window. This alone does not establish recovery.",
    "jacket_warming": "Jacket temperature increased by at least 3 DEG C across the simulation window.",
    "feed_flow_increased": "Reactor feed flow increased by at least 5 M3/H across the simulation window.",
    "tank_level_increased": "Feed-tank level increased by at least 3 percentage points across the simulation window.",
    "coolant_output_high": "The latest coolant-controller output indication is at least 95 percent. An output command is not proof of valve position or available cooling.",
    "cooling_path_unconfirmed": "Rising reactor and jacket temperatures coincide with a high coolant output indication. Cooling impairment is a hypothesis; these measurements do not distinguish utility loss, valve response, instrumentation, or other causes.",
    "reactor_below_window_peak": "The reactor rose and then ended at least 2 DEG C below an earlier window peak. This does not establish that recovery is complete.",
    "no_large_net_change": "No project-threshold-sized net change appears in reactor temperature, jacket temperature, feed flow, or tank level. This is not proof of a safe or undisturbed process.",
    "history_quality_gap": "The history contains unreliable measurements. Trend-based conclusions are withheld even though the latest snapshot passed its quality checks.",
    "cause_unresolved": "This bounded observation window cannot establish a unique root cause or rule out an unobserved fault.",
}
TREND_RULES = {
    "profile": "ess-u1-window-v1",
    "reactor_warming": "last TIC201 minus first TIC201 >= 2 DEG C",
    "reactor_cooling": "last TIC201 minus first TIC201 <= -2 DEG C",
    "jacket_warming": "last TIC202 minus first TIC202 >= 3 DEG C",
    "feed_flow_increased": "last FIC102 minus first FIC102 >= 5 M3/H",
    "tank_level_increased": "last LIC101 minus first LIC101 >= 3 percentage points",
    "coolant_output_high": "latest TIC202.OP >= 95 percent",
    "cooling_path_unconfirmed": "reactor_warming AND jacket_warming AND coolant_output_high",
    "reactor_below_window_peak": "max TIC201 minus first TIC201 >= 2 AND max TIC201 minus last TIC201 >= 2",
    "no_large_net_change": "absolute net changes: TIC201 < 2, TIC202 < 3, FIC102 < 5, LIC101 < 3",
    "history_quality_gap": "any historical quality is not good: emit this and cause_unresolved, with no other trend findings",
    "cause_unresolved": "always include for a history assessment",
    "checks": "Always compare_independent_measurement; add review_cooling_evidence for cooling_path_unconfirmed; add review_feed_balance for feed_flow_increased or tank_level_increased; add monitor_thermal_recovery for reactor_cooling or reactor_below_window_peak; add capture_clean_window for history_quality_gap. Retain snapshot checks. Remove duplicates.",
    "evidence": "Include all five history:TAG references as well as snapshot:alarms and policy:lab-v2.",
}
POLICY = {
    "id": "lab-advisory-policy-v2",
    "findings": FINDINGS,
    "checks": CHECKS,
    "demo_rule": "demo-cooling-v1 ONLY: TT101 > 80 degC AND FT102 < 20 L/min",
    "trend_rules": TREND_RULES,
    "provenance": "Project-authored synthetic research policy, 2026-09-20. Not a plant procedure or ISA limit.",
}
POLICY_HASH = digest(POLICY)
POLICY_REF = "policy:lab-v2"


def eligible(snapshot):
    tags = {row["id"]: row for row in snapshot["tags"]}
    refs = {f"tag:{tag}": row for tag, row in tags.items()}
    refs["snapshot:alarms"] = snapshot["alarms"]
    refs[POLICY_REF] = {"id": POLICY["id"], "sha256": POLICY_HASH}
    finding = "reported_alarms" if snapshot["alarms"] else "no_reported_alarms"
    findings = [finding]
    checks = ["inspect_alarm_context", "compare_independent_measurement"] if snapshot["alarms"] else ["continue_observation"]
    evidence = ["snapshot:alarms", POLICY_REF]
    if snapshot["profile"] == "demo-cooling-v1" and tags["TT101"]["value"] > 80 and tags["FT102"]["value"] < 20:
        findings.append("cooling_mismatch")
        checks = ["review_cooling_evidence", "compare_independent_measurement"] + (["inspect_alarm_context"] if snapshot["alarms"] else [])
        evidence += ["tag:TT101", "tag:FT102"]
    if snapshot["profile"] == "ess-u1-window-v1":
        trend_findings, trend_checks, trend_refs = history_findings(snapshot)
        findings += trend_findings
        checks = list(dict.fromkeys(checks + trend_checks))
        evidence += list(trend_refs)
        refs.update(trend_refs)
    return findings, checks, evidence, refs


def history_findings(snapshot):
    history = snapshot["history"]
    samples = history["samples"]
    units = {tag["id"]: tag["unit"] for tag in snapshot["tags"]}
    refs = {f"history:{tag}": {
        "clock": history["clock"], "epoch_id": history["epoch_id"], "unit": units[tag],
        "samples": [{"sequence": s["sequence"], "elapsed_s": s["elapsed_s"], "value": s["values"][tag], "quality": s["quality"][tag]} for s in samples],
    } for tag in ("TIC201", "TIC202", "FIC102", "LIC101", "TIC202.OP")}
    if any(q != "good" for s in samples for q in s["quality"].values()):
        return ["history_quality_gap", "cause_unresolved"], ["capture_clean_window", "compare_independent_measurement"], refs
    delta = {tag: round(samples[-1]["values"][tag] - samples[0]["values"][tag], 6) for tag in samples[0]["values"]}
    findings, checks = [], ["compare_independent_measurement"]
    for tag, threshold, finding in (("TIC201", 2, "reactor_warming"), ("TIC202", 3, "jacket_warming"),
                                    ("FIC102", 5, "feed_flow_increased"), ("LIC101", 3, "tank_level_increased")):
        if delta[tag] >= threshold: findings.append(finding)
    if delta["TIC201"] <= -2: findings.append("reactor_cooling")
    if samples[-1]["values"]["TIC202.OP"] >= 95: findings.append("coolant_output_high")
    if {"reactor_warming", "jacket_warming", "coolant_output_high"}.issubset(findings):
        findings.append("cooling_path_unconfirmed"); checks.append("review_cooling_evidence")
    reactor = [s["values"]["TIC201"] for s in samples]
    if round(max(reactor) - reactor[0], 6) >= 2 and round(max(reactor) - reactor[-1], 6) >= 2:
        findings.append("reactor_below_window_peak")
    if all(abs(delta[tag]) < threshold for tag, threshold in (("TIC201", 2), ("TIC202", 3), ("FIC102", 5), ("LIC101", 3))):
        findings.append("no_large_net_change")
    if {"feed_flow_increased", "tank_level_increased"}.intersection(findings): checks.append("review_feed_balance")
    if {"reactor_cooling", "reactor_below_window_peak"}.intersection(findings): checks.append("monitor_thermal_recovery")
    findings.append("cause_unresolved")
    return findings, checks, refs
