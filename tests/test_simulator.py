"""Opt-in integration with the user's trusted simulator checkout, never a plant."""
import json
import os
from pathlib import Path
import subprocess
import unittest
from moa.engine import Agent
from moa.evidence import EvidenceStore
from moa.drills import evaluate_drills
from moa.providers import Baseline


@unittest.skipUnless(os.environ.get("MOA_SIM_REPO"), "Set MOA_SIM_REPO to a trusted local simulator checkout")
class SimulatorTests(unittest.TestCase):
    def test_normal_and_bad_quality_operator_projection(self):
        for scenario, status in (("normal", "advisory"), ("bad-quality", "abstain")):
            with self.subTest(scenario=scenario):
                exported = subprocess.run(["node", "scripts/export_sim.cjs", os.environ["MOA_SIM_REPO"], scenario],
                                          cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True, timeout=30)
                data = json.loads(exported.stdout)
                self.assertEqual(data["source"]["adapter"], "ess-v1")
                self.assertEqual(len(data["source"]["revision"]), 40)
                for excluded in ("archFaults", "instructor", "fault_ids", "probableCause", "correctiveAction"):
                    self.assertNotIn(excluded, exported.stdout)
                store = EvidenceStore(":memory:")
                try:
                    result = Agent(store).assess(data)
                    self.assertEqual(result["status"], status, result)
                    if scenario == "bad-quality": self.assertEqual(result["reason"], "quality")
                finally: store.close()

    def test_window_export_is_reproducible_without_scenario_answers(self):
        exports = []
        for _ in range(2):
            process = subprocess.run(["node", "scripts/export_trajectory.cjs", os.environ["MOA_SIM_REPO"], "cooling-loss", "20260920"],
                                     cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True, timeout=30)
            observation, receipt = json.loads(process.stdout), json.loads(process.stderr)
            self.assertEqual(observation["schema_version"], "1.1")
            self.assertNotIn("cooling-loss", process.stdout)
            self.assertNotIn('"seed"', process.stdout)
            self.assertNotIn('"fault"', process.stdout)
            exports.append((observation, receipt))
        self.assertEqual(exports[0][1]["trajectory_sha256"], exports[1][1]["trajectory_sha256"])
        self.assertEqual(exports[0][0]["history"]["samples"], exports[1][0]["history"]["samples"])
        self.assertNotEqual(exports[0][0]["history"]["epoch_id"], exports[1][0]["history"]["epoch_id"])

    def test_development_oracle_and_no_label_leakage(self):
        class RecordingBaseline(Baseline):
            def __init__(self): self.seen = []
            def respond(self, messages):
                self.seen.append(json.dumps(messages))
                return super().respond(messages)
        provider = RecordingBaseline()
        report = evaluate_drills(os.environ["MOA_SIM_REPO"], provider)
        self.assertTrue(report["passed"], [(r["id"], r["actual"]["reason"]) for r in report["cases"] if not r["passed"]])
        self.assertEqual(report["metrics"]["useful_assessment"], {"passed": 10, "total": 10})
        self.assertEqual(report["metrics"]["input_guards"], {"passed": 8, "total": 8})
        self.assertEqual(report["metrics"]["unexpected_advisories"], 0)
        for blob in provider.seen:
            for hidden in ('"expected"', '"generator"', '"seeds"', "restoration-lag", "cooling-loss", "feed-surge"):
                self.assertNotIn(hidden, blob)

    def test_always_refuse_fails_development_usefulness(self):
        class AlwaysRefuse:
            name = "negative-control"
            def respond(self, messages): return {"kind": "abstain", "reason": "insufficient_evidence"}
        report = evaluate_drills(os.environ["MOA_SIM_REPO"], AlwaysRefuse())
        self.assertFalse(report["passed"])
        self.assertEqual(report["metrics"]["useful_assessment"]["passed"], 0)
        self.assertEqual(report["metrics"]["input_guards"]["passed"], 8)
        self.assertEqual(report["metrics"]["voluntary_abstentions"], 10)


if __name__ == "__main__": unittest.main()
