"""Opt-in integration with the user's trusted simulator checkout, never a plant."""
import json
import os
from pathlib import Path
import subprocess
import unittest
from moa.engine import Agent
from moa.evidence import EvidenceStore


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


if __name__ == "__main__": unittest.main()
