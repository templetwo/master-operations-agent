import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from moa.comparison import compare, inference_metrics, pair_reports


class ComparisonTests(unittest.TestCase):
    def test_pairing_detects_changed_data_order_or_labels(self):
        baseline = {"cases": [{"id": "one", "expected": {"status": "advisory"}, "process_data_sha256": "a"}], "provider": "baseline"}
        self.assertTrue(all(r["matched"] for r in pair_reports(baseline, baseline, baseline)))
        for field, value in (("id", "two"), ("expected", {}), ("process_data_sha256", "b")):
            altered = copy.deepcopy(baseline); altered["cases"][0][field] = value
            self.assertFalse(pair_reports(baseline, altered, baseline)[0]["matched"])
        empty = dict(baseline, cases=[])
        self.assertFalse(pair_reports(baseline, empty, baseline)[0]["matched"])

    def test_unavailable_token_counters_are_not_zero(self):
        report = {"evidence": {"events": [{"payload": {"kind": "provider_call", "data": {"wall_ms": 50}}}]}}
        metrics = inference_metrics(report)
        self.assertEqual(metrics["calls"], 1)
        self.assertIsNone(metrics["server_reported_totals"]["eval_count"])

    def test_existing_output_is_preserved_without_network(self):
        with tempfile.TemporaryDirectory() as directory, patch("moa.comparison.Ollama.request") as request:
            marker = Path(directory) / "receipt.json"; marker.write_text("original")
            with self.assertRaises(FileExistsError): compare("unused", "local:1b", "a" * 64, directory)
            request.assert_not_called()
            self.assertEqual(marker.read_text(), "original")

    def test_setup_failure_preserves_manifest(self):
        with tempfile.TemporaryDirectory() as directory, patch("moa.comparison.Ollama.request", side_effect=ValueError("offline")):
            output = Path(directory) / "trial"
            with self.assertRaises(ValueError): compare("unused", "local:1b", "a" * 64, output)
            manifest = json.loads((output / "run.json").read_text())
            self.assertEqual(manifest["status"], "interrupted")
            self.assertFalse((output / "comparison.json").exists())

    def test_completed_model_score_cannot_hide_mismatched_inputs(self):
        def score(sim_repo, active, store, checkpoint):
            control = active.name == "always-refuse-negative-control"
            row = {"id": "normal", "expected": {"status": "advisory"},
                   "process_data_sha256": "different" if active.name.startswith("ollama:") else "same"}
            checkpoint(row)
            return {"provider": active.name, "passed": not control, "cases": [row],
                    "metrics": {"useful_assessment": {"passed": 0 if control else 1, "total": 1}},
                    "evidence": {"anchor": {"events": 0, "head": "0" * 64}, "events": []}}
        with tempfile.TemporaryDirectory() as directory, \
             patch("moa.comparison.Ollama.request", return_value={"version": "test", "models": []}), \
             patch("moa.comparison.Ollama.prepare", return_value={"digest": "a" * 64}), \
             patch("moa.comparison.Ollama.respond", return_value={"kind": "tool", "name": "read_snapshot", "arguments": {}}), \
             patch("moa.comparison.evaluate_drills", side_effect=score):
            output = Path(directory) / "trial"
            report = compare("unused", "local:1b", "a" * 64, output)
            self.assertTrue(report["completed"])
            self.assertTrue(report["reports"]["local-model"]["passed"])
            self.assertFalse(report["comparison_valid"])
            self.assertFalse(report["local_passed_development"])
            self.assertTrue((output / "local-model.progress.jsonl").exists())


if __name__ == "__main__": unittest.main()
