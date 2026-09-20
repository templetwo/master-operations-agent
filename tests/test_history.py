import copy
import json
import unittest
from moa.contracts import Rejected, validate_snapshot
from moa.drills import MANIFEST_PATH, evidence_matches, score_case
from moa.engine import Agent, ReadTools
from moa.evidence import EvidenceStore
from moa.fixtures import window_fixture, fixture
from test_core import Sequence, READ_SNAPSHOT, READ_POLICY


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.store = EvidenceStore(":memory:")
        self.addCleanup(self.store.close)

    def assess(self, data=None, provider=None):
        return Agent(self.store, provider).assess(data or window_fixture())

    def test_thermal_pattern_is_a_hypothesis_not_a_proven_cause(self):
        result = self.assess()
        self.assertEqual(result["status"], "advisory")
        self.assertEqual({f["id"] for f in result["findings"]}, {"reported_alarms", "reactor_warming", "jacket_warming", "coolant_output_high", "cooling_path_unconfirmed", "cause_unresolved"})
        self.assertEqual({c["id"] for c in result["checks"]}, {"inspect_alarm_context", "compare_independent_measurement", "review_cooling_evidence"})
        self.assertTrue(evidence_matches(window_fixture(), result))

    def test_falling_temperature_does_not_authorize_return_to_service(self):
        result = self.assess(window_fixture("trend-recovery"))
        self.assertIn("reactor_cooling", {f["id"] for f in result["findings"]})
        self.assertNotIn("cooling_path_unconfirmed", {f["id"] for f in result["findings"]})
        check = next(c for c in result["checks"] if c["id"] == "monitor_thermal_recovery")
        self.assertIn("does not prove recovery", check["text"])

    def test_history_read_is_required_and_snapshot_does_not_leak_it(self):
        snapshot = window_fixture()
        boundary = ReadTools(snapshot, lambda *args: None)
        self.assertNotIn("history", boundary.call("read_snapshot", {}))
        history = boundary.call("read_history", {})
        history["samples"][0]["values"]["TIC201"] = -100
        self.assertEqual(boundary.call("read_history", {})["samples"][0]["values"]["TIC201"], 150)
        good = self.assess(snapshot)
        candidate = {"kind": "advice", "finding_ids": [f["id"] for f in good["findings"]],
                     "check_ids": [c["id"] for c in good["checks"]], "evidence": [e["ref"] for e in good["evidence"]]}
        self.assertEqual(self.assess(snapshot, Sequence(READ_SNAPSHOT, READ_POLICY, candidate))["reason"], "ungrounded")

    def test_bad_historical_quality_narrows_advice_without_using_bad_values(self):
        result = self.assess(window_fixture("history-quality"))
        self.assertEqual(result["status"], "advisory")
        self.assertEqual({f["id"] for f in result["findings"]}, {"reported_alarms", "history_quality_gap", "cause_unresolved"})
        self.assertIn("capture_clean_window", {c["id"] for c in result["checks"]})

    def test_missing_reversed_or_duplicate_samples_are_not_trends(self):
        for mutation in (lambda h: h["samples"].pop(3), lambda h: h["samples"].reverse(),
                         lambda h: h["samples"][3].update(sequence=2)):
            data = window_fixture(); mutation(data["history"])
            self.assertEqual(self.assess(data)["reason"], "history_sequence")

    def test_current_and_historical_endpoints_must_match(self):
        data = window_fixture(); data["history"]["samples"][-1]["values"]["TIC201"] = 30
        self.assertEqual(self.assess(data)["reason"], "history_mismatch")

    def test_time_gaps_and_clock_mixing_rejected(self):
        data = window_fixture(); data["history"]["samples"][2]["elapsed_s"] = 21
        self.assertEqual(self.assess(data)["reason"], "history_timing")
        data = window_fixture(); data["history"]["clock"] = "wall_clock"
        self.assertEqual(self.assess(data)["reason"], "history_clock")

    def test_unknown_truth_fields_and_downgrades_rejected(self):
        for mutate in (lambda d: d["history"].update(fault="cool"), lambda d: d.update(schema_version="1.0"),
                       lambda d: d.update(profile="ess-u1-v1"), lambda d: d["history"]["samples"][0].update(instructor="answer")):
            data = window_fixture(); mutate(data)
            self.assertEqual(self.assess(data)["status"], "abstain")

    def test_non_finite_boolean_and_missing_historical_values_rejected(self):
        for value in (float("inf"), True, "open valve", None):
            data = window_fixture(); data["history"]["samples"][1]["values"]["TIC201"] = value
            self.assertEqual(self.assess(data)["status"], "abstain")

    def test_earlier_peak_is_not_hidden_by_equal_endpoints(self):
        data = window_fixture()
        for sample in data["history"]["samples"]:
            sample["values"].update(TIC201=150, TIC202=40, **{"TIC202.OP": 70})
        data["history"]["samples"][6]["values"]["TIC201"] = 160
        for tag in data["tags"]: tag["value"] = data["history"]["samples"][-1]["values"][tag["id"]]
        findings = {f["id"] for f in self.assess(data)["findings"]}
        self.assertIn("reactor_below_window_peak", findings)
        self.assertIn("no_large_net_change", findings)
        self.assertNotIn("reactor_warming", findings)

    def test_single_snapshot_cannot_call_history(self):
        boundary = ReadTools(fixture(), lambda *args: None)
        with self.assertRaises(Rejected): boundary.call("read_history", {})

    def test_scorecard_rejects_forged_evidence_and_blanket_abstention(self):
        data = window_fixture(); good = self.assess(data)
        expected = {"status": "advisory", "reason": "supported", "findings": [f["id"] for f in good["findings"]], "checks": [c["id"] for c in good["checks"]]}
        case = {"id": "test", "expected": expected, "observation": data, "generator": {}}
        bad = copy.deepcopy(good); bad["evidence"][-1]["value"]["samples"][0]["value"] = -999
        self.assertFalse(score_case(case, bad)["passed"])
        refusal = self.assess(data, Sequence({"kind": "abstain", "reason": "insufficient_evidence"}))
        self.assertFalse(score_case(case, refusal)["passed"])

    def test_manifest_labels_do_not_claim_independent_review(self):
        manifest = json.loads(MANIFEST_PATH.read_text())
        self.assertEqual(manifest["review_status"], "controls_review_pending")
        self.assertEqual(manifest["split"], "development")


if __name__ == "__main__": unittest.main()
