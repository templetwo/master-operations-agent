"""Reviewed research policy v1. These checks never authorize equipment changes."""

from .contracts import digest

CHECKS = {
    "inspect_alarm_context": "Review the reported alarm conditions and their operator procedure in the simulator.",
    "compare_independent_measurement": "Compare an independent simulator indication before accepting a causal explanation.",
    "review_cooling_evidence": "Inspect the simulator cooling indications and trend history. The two values do not establish a root cause.",
    "continue_observation": "Continue observing the simulator. An empty alarm list does not establish a safe process.",
}
FINDINGS = {
    "reported_alarms": "The snapshot reports alarm records. Their presence alone does not establish the initiating cause.",
    "no_reported_alarms": "The snapshot reports no alarms within its declared coverage.",
    "cooling_mismatch": "The demo temperature is above 80 degC while demo coolant flow is below 20 L/min. Possible cooling impairment needs independent confirmation.",
}
POLICY = {
    "id": "lab-advisory-policy-v1",
    "findings": FINDINGS,
    "checks": CHECKS,
    "demo_rule": "demo-cooling-v1 ONLY: TT101 > 80 degC AND FT102 < 20 L/min",
    "provenance": "Project-authored synthetic research policy, 2026-09-20. Not a plant procedure or ISA limit.",
}
POLICY_HASH = digest(POLICY)


def eligible(snapshot):
    tags = {row["id"]: row for row in snapshot["tags"]}
    refs = {f"tag:{tag}": row for tag, row in tags.items()}
    refs["snapshot:alarms"] = snapshot["alarms"]
    refs["policy:lab-v1"] = {"id": POLICY["id"], "sha256": POLICY_HASH}
    finding = "reported_alarms" if snapshot["alarms"] else "no_reported_alarms"
    findings = [finding]
    checks = ["inspect_alarm_context", "compare_independent_measurement"] if snapshot["alarms"] else ["continue_observation"]
    evidence = ["snapshot:alarms", "policy:lab-v1"]
    if snapshot["profile"] == "demo-cooling-v1" and tags["TT101"]["value"] > 80 and tags["FT102"]["value"] < 20:
        findings.append("cooling_mismatch")
        checks = ["review_cooling_evidence", "compare_independent_measurement"] + (["inspect_alarm_context"] if snapshot["alarms"] else [])
        evidence += ["tag:TT101", "tag:FT102"]
    return findings, checks, evidence, refs
