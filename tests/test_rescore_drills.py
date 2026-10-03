import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.rescore_drills import compare_rows, effective_manifest, receipt_rows

ROOT = Path(__file__).resolve().parents[1]
PIN = "3aad7695b8720b291999ef0903fcab7b7e008f1e"
OTHER = "bfed001fc89d9beaa640b30a7886d5f16f61a31b"
MANIFEST = {"suite": "s", "simulator_revision": PIN, "seeds": [1], "cases": []}
ROW = {"id": "normal:1", "passed": True,
       "expected": {"status": "advisory", "reason": "supported", "findings": ["b", "a"], "checks": ["c"]},
       "actual": {"status": "advisory", "reason": "supported", "findings": [{"id": "a", "text": "A."}, {"id": "b", "text": "B."}],
                  "checks": [{"id": "c", "text": "C."}], "evidence": [{"ref": "x", "value": 1}]},
       "process_data_sha256": "p" * 64, "observation_sha256": "o" * 64, "evidence_fidelity": True, "generator": {}}


class RevisionOverrideTests(unittest.TestCase):
    def test_mismatched_revision_is_refused_without_explicit_flag(self):
        with self.assertRaises(ValueError):
            effective_manifest(MANIFEST, OTHER, allow_mismatch=False)

    def test_override_is_recorded_and_leaves_manifest_unchanged(self):
        original = copy.deepcopy(MANIFEST)
        scored, override = effective_manifest(MANIFEST, OTHER, allow_mismatch=True)
        self.assertEqual(scored["simulator_revision"], OTHER)
        self.assertEqual(override, {"pinned_revision": PIN, "scored_revision": OTHER,
                                    "note": "Expectations applied unchanged to a revision they were not written for. A miss is reported, not absorbed."})
        self.assertEqual(MANIFEST, original)

    def test_matching_revision_is_not_an_override(self):
        scored, override = effective_manifest(MANIFEST, PIN, allow_mismatch=False)
        self.assertEqual(scored, MANIFEST)
        self.assertIsNone(override)


class RowComparisonTests(unittest.TestCase):
    def test_receipt_rows_keep_ids_and_drop_rendered_evidence(self):
        self.assertEqual(receipt_rows([ROW]), [{
            "id": "normal:1", "passed": True,
            "expected": {"status": "advisory", "reason": "supported", "findings": ["b", "a"], "checks": ["c"]},
            "actual": {"status": "advisory", "reason": "supported", "findings": ["a", "b"], "checks": ["c"]},
            "process_data_sha256": "p" * 64, "observation_sha256": "o" * 64, "evidence_fidelity": True}])

    def test_identical_rows_compare_clean(self):
        rows = receipt_rows([ROW])
        recorded = [{"id": "normal:1", "passed": True,
                     "expected": {"status": "advisory", "reason": "supported", "findings": ["a", "b"]},
                     "actual": {"status": "advisory", "reason": "supported", "findings": ["b", "a"]},
                     "tic202": {"quality": "good", "value": 40.0}, "process_data_sha256": "p" * 64, "evidence_fidelity": True}]
        self.assertEqual(compare_rows(rows, recorded), [])

    def test_each_changed_field_and_missing_row_is_named(self):
        rows = receipt_rows([ROW])
        recorded = [{"id": "normal:1", "passed": False,
                     "expected": {"status": "advisory", "reason": "supported", "findings": ["a", "b"]},
                     "actual": {"status": "abstain", "reason": "quality", "findings": []},
                     "process_data_sha256": "q" * 64, "evidence_fidelity": True},
                    {"id": "cooling-loss:1", "passed": False}]
        fields = [(m["id"], m["field"]) for m in compare_rows(rows, recorded)]
        self.assertEqual(fields, [("normal:1", "passed"), ("normal:1", "actual.status"), ("normal:1", "actual.reason"),
                                  ("normal:1", "actual.findings"), ("normal:1", "process_data_sha256"), ("cooling-loss:1", "id")])

    def test_row_absent_from_the_receipt_is_named(self):
        self.assertEqual(compare_rows(receipt_rows([ROW]), []),
                         [{"id": "normal:1", "field": "id", "recorded": None, "actual": "normal:1"}])


@unittest.skipUnless(os.environ.get("MOA_SIM_REPO"), "Set MOA_SIM_REPO to a trusted local simulator checkout")
class RescoreEndToEndTests(unittest.TestCase):
    def setUp(self):
        revision = subprocess.run(["git", "-C", os.environ["MOA_SIM_REPO"], "rev-parse", "HEAD"],
                                  capture_output=True, text=True, check=True).stdout.strip()
        if revision != OTHER:
            self.skipTest("The recorded source-map v2 receipt was scored at simulator bfed001.")

    def run_script(self, *args):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "rescore.json"
            process = subprocess.run([sys.executable, "scripts/rescore_drills.py", os.environ["MOA_SIM_REPO"], "--out", str(out), *args],
                                     cwd=ROOT, capture_output=True, text=True, timeout=300)
            return process, json.loads(out.read_text()) if out.exists() else None

    def test_v1_override_reproduces_the_recorded_source_map_v2_rows(self):
        process, report = self.run_script("--manifest", "moa/data/drills-v1.json", "--allow-revision-mismatch",
                                          "--compare", "receipts/source-map-v2/evaluation.json")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report["comparison"]["mismatches"], [])
        self.assertEqual(report["revision_override"]["pinned_revision"], PIN)
        self.assertEqual(report["metrics"]["useful_assessment"], {"passed": 8, "total": 10})
        self.assertEqual(report["metrics"]["input_guards"], {"passed": 8, "total": 8})

    def test_v2_scores_without_override(self):
        process, report = self.run_script("--manifest", "moa/data/drills-v2.json")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIsNone(report["revision_override"])
        self.assertEqual(report["metrics"]["useful_assessment"], {"passed": 8, "total": 8})
        self.assertEqual(report["metrics"]["input_guards"], {"passed": 10, "total": 10})

    def test_always_refuse_control_fails_usefulness_and_passes_guards(self):
        process, report = self.run_script("--manifest", "moa/data/drills-v2.json", "--provider", "always-refuse")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report["provider"], "always-refuse-negative-control")
        self.assertFalse(report["passed"])
        self.assertEqual(report["metrics"]["useful_assessment"], {"passed": 0, "total": 8})
        self.assertEqual(report["metrics"]["input_guards"], {"passed": 10, "total": 10})
        self.assertEqual(report["metrics"]["voluntary_abstentions"], 8)

    def test_mismatch_without_flag_exits_nonzero_and_writes_nothing(self):
        process, report = self.run_script("--manifest", "moa/data/drills-v1.json")
        self.assertNotEqual(process.returncode, 0)
        self.assertIsNone(report)


if __name__ == "__main__":
    unittest.main()
