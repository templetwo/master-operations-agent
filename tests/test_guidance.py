"""Authored policy examples, not baseline-generated expectations or holdouts."""

import unittest

from moa.contracts import Rejected, validate_snapshot
from moa.engine import validate_candidate
from moa.fixtures import fixture, window_fixture
from moa.guidance import OUTPUT_CONTRACT_GUIDANCE, POLICY_GUIDANCE
from moa.knowledge import CHECKS, FINDINGS, POLICY_HASH, eligible


WINDOW_REFS = {"snapshot:alarms", "policy:lab-v2", "history:TIC201",
               "history:TIC202", "history:FIC102", "history:LIC101", "history:TIC202.OP"}


def authored_window(rows, *, alarms=False, bad_history=False):
    """Use fixture metadata only; all process values are supplied by the table."""
    data = window_fixture()
    data["alarms"] = data["alarms"] if alarms else []
    samples = []
    names = ("TIC201", "TIC202", "FIC102", "LIC101", "TIC202.OP")
    for index, row in enumerate(rows):
        samples.append({"sequence": index, "elapsed_s": index * 10,
                        "values": dict(zip(names, row)), "quality": dict.fromkeys(names, "good")})
    if bad_history:
        samples[1]["quality"]["TIC201"] = "bad"
        samples[1]["values"]["TIC201"] = None
    data["history"].update(samples=samples, sequence=len(samples) - 1)
    for tag in data["tags"]:
        tag["value"] = samples[-1]["values"][tag["id"]]
    return validate_snapshot(data)


class GuidanceTests(unittest.TestCase):
    def test_catalog_is_covered_but_output_factor_contains_no_answer_ids(self):
        for identifier in (*FINDINGS, *CHECKS):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, POLICY_GUIDANCE)
                self.assertNotIn(identifier, OUTPUT_CONTRACT_GUIDANCE)
        self.assertNotIn("history:TIC201", OUTPUT_CONTRACT_GUIDANCE)
        self.assertIn("1 through 16 unique strings", OUTPUT_CONTRACT_GUIDANCE)
        self.assertIn("not type", OUTPUT_CONTRACT_GUIDANCE)
        self.assertIn("Python round", POLICY_GUIDANCE)

    def test_policy_identity_is_unchanged(self):
        self.assertEqual(POLICY_HASH, "4a4242bbaa82b5d52e1336451b467d3ac8dff51fcb7999c6f940b5e90cd39ef1")

    def test_authored_demo_cases_capture_replacement_and_strict_boundaries(self):
        cases = [
            (False, 65, 45, {"no_reported_alarms"}, {"continue_observation"}, False),
            (True, 65, 45, {"reported_alarms"}, {"inspect_alarm_context", "compare_independent_measurement"}, False),
            (False, 81, 19, {"no_reported_alarms", "cooling_mismatch"}, {"review_cooling_evidence", "compare_independent_measurement"}, True),
            (True, 81, 19, {"reported_alarms", "cooling_mismatch"}, {"inspect_alarm_context", "review_cooling_evidence", "compare_independent_measurement"}, True),
            (False, 80, 19, {"no_reported_alarms"}, {"continue_observation"}, False),
            (False, 81, 20, {"no_reported_alarms"}, {"continue_observation"}, False),
        ]
        for alarms, temperature, flow, findings, checks, mismatch in cases:
            with self.subTest(alarms=alarms, temperature=temperature, flow=flow):
                data = fixture("cooling")
                if not alarms:
                    data["alarms"] = []
                data["tags"][0]["value"] = temperature
                data["tags"][1]["value"] = flow
                actual_findings, actual_checks, refs, _ = eligible(validate_snapshot(data))
                self.assertEqual(set(actual_findings), findings)
                self.assertEqual(set(actual_checks), checks)
                self.assertEqual(set(refs), {"snapshot:alarms", "policy:lab-v2"} |
                                 ({"tag:TT101", "tag:FT102"} if mismatch else set()))

    def test_authored_window_table(self):
        stable = (100, 40, 60, 50, 70)
        cases = [
            ("quiet", [stable] * 4, {"no_large_net_change"}, set()),
            ("thermal", [stable, stable, stable, (102, 43, 60, 50, 95)],
             {"reactor_warming", "jacket_warming", "coolant_output_high", "cooling_path_unconfirmed"},
             {"review_cooling_evidence"}),
            ("feed-level", [stable, stable, stable, (100, 40, 65, 53, 70)],
             {"feed_flow_increased", "tank_level_increased"}, {"review_feed_balance"}),
            ("cooling", [stable, stable, stable, (98, 40, 60, 50, 70)],
             {"reactor_cooling"}, {"monitor_thermal_recovery"}),
            ("interior-peak", [stable, (102, 40, 60, 50, 95), stable, (100, 40, 60, 50, 95)],
             {"reactor_below_window_peak", "no_large_net_change", "coolant_output_high"},
             {"monitor_thermal_recovery"}),
            ("rounded-threshold", [stable, stable, stable, (101.9999996, 40, 60, 50, 70)],
             {"reactor_warming"}, set()),
            ("below-rounded-threshold", [stable, stable, stable, (101.9999994, 40, 60, 50, 70)],
             {"no_large_net_change"}, set()),
            ("unrounded-output", [stable, stable, stable, (100, 40, 60, 50, 94.9999996)],
             {"no_large_net_change"}, set()),
            ("negative-feed", [stable, stable, stable, (100, 40, 55, 50, 70)], set(), set()),
        ]
        for name, rows, trend_findings, trend_checks in cases:
            with self.subTest(case=name):
                findings, checks, evidence, _ = eligible(authored_window(rows))
                self.assertEqual(set(findings), {"no_reported_alarms", "cause_unresolved"} | trend_findings)
                self.assertEqual(set(checks), {"continue_observation", "compare_independent_measurement"} | trend_checks)
                self.assertEqual(set(evidence), WINDOW_REFS)

    def test_historical_quality_suppresses_all_numeric_window_findings(self):
        rows = [(100, 40, 60, 50, 70), (101, 41, 61, 51, 90),
                (105, 45, 65, 53, 98), (108, 48, 70, 56, 98)]
        findings, checks, evidence, _ = eligible(authored_window(rows, alarms=True, bad_history=True))
        self.assertEqual(set(findings), {"reported_alarms", "history_quality_gap", "cause_unresolved"})
        self.assertEqual(set(checks), {"inspect_alarm_context", "capture_clean_window", "compare_independent_measurement"})
        self.assertEqual(set(evidence), WINDOW_REFS)

    def test_authored_advice_is_accepted_but_extra_check_remains_rejected(self):
        snapshot = fixture("normal")
        answer = {"kind": "advice", "finding_ids": ["no_reported_alarms"],
                  "check_ids": ["continue_observation"], "evidence": ["snapshot:alarms", "policy:lab-v2"]}
        reads = {"read_snapshot", "read_policy"}
        self.assertEqual(validate_candidate(answer, snapshot, reads)["status"], "advisory")
        answer["check_ids"].append("capture_clean_window")
        with self.assertRaises(Rejected) as raised:
            validate_candidate(answer, snapshot, reads)
        self.assertEqual(raised.exception.code, "unsupported_check")


if __name__ == "__main__":
    unittest.main()
