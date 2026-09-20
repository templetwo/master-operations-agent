"""Independent offline reader checks, using authored fixtures, not policy helpers."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from moa.diagnostics import DiagnosticError, diagnose_file, diagnose_report

ROOT = Path(__file__).resolve().parents[1]


def fixture(candidate=None, expected_status="advisory", reason="schema", later_call=False):
    previous = "0" * 64
    events = []
    actual = {"run_id": "r1", "status": "abstain", "reason": reason}
    payloads = [("run_started", {})]
    if candidate is not None:
        payloads.append(("provider_response", {"response": candidate}))
    if later_call:
        payloads.append(("provider_call", {"rejection_code": "invalid_json"}))
    payloads.append(("outcome", actual))
    for number, (kind, data) in enumerate(payloads, 1):
        event = {"seq": number, "previous": previous, "payload": {"run_id": "r1", "at": "2026-09-20T00:00:00Z", "kind": kind, "data": copy.deepcopy(data)}}
        event["hash"] = hashlib.sha256(json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()).hexdigest()
        events.append(event)
        previous = event["hash"]
    actual["receipt"] = {"seq": len(events), "hash": previous}
    expected = {"status": expected_status, "findings": ["f1", "f2"] if expected_status == "advisory" else [],
                "checks": ["c1"] if expected_status == "advisory" else []}
    return {"provider": "test", "passed": False, "cases": [{"id": "case1", "expected": expected, "actual": actual, "passed": False}],
            "evidence": {"events": events, "anchor": {"events": len(events), "head": previous}}}


def advice(**updates):
    return dict({"kind": "advice", "finding_ids": ["f1", "f2"], "check_ids": ["c1"], "evidence": ["e1"]}, **updates)


class DiagnosticTests(unittest.TestCase):
    def test_exact_content_does_not_change_release(self):
        original = fixture(advice())
        before = copy.deepcopy(original)
        report = diagnose_report(original)
        self.assertEqual(original, before)
        self.assertFalse(report["original_report_passed"])
        self.assertEqual(report["cases"][0]["original_release_reason"], "schema")
        self.assertEqual(report["summary"]["original"]["findings"]["exact_sets"], 1)

    def test_coverage_extras_omissions_and_denominators(self):
        report = diagnose_report(fixture(advice(finding_ids=["f1", "extra"], check_ids=[])))
        fields = report["summary"]["original"]
        self.assertEqual(fields["findings"]["micro_recall"], .5)
        self.assertEqual(fields["findings"]["micro_precision"], .5)
        self.assertEqual(fields["findings"]["extras"], 1)
        self.assertEqual(fields["findings"]["omitted"], 1)
        self.assertEqual(fields["checks"]["micro_recall"], 0)
        self.assertIsNone(fields["checks"]["micro_precision"])
        self.assertFalse(report["cases"][0]["original"]["envelope"]["valid"])

    def test_wrapping_and_type_repair_are_explicit_and_offline(self):
        for candidate, transform in ((advice(type="json_object"), "remove_type_json_object"),
                                     ({"type": "json_object", "content": advice()}, "unwrap_type_json_object_content")):
            report = diagnose_report(fixture(candidate))
            row = report["cases"][0]
            self.assertFalse(row["original"]["envelope"]["valid"])
            self.assertEqual(row["offline_packaging_diagnostic"]["transformations"], [transform])
            self.assertTrue(row["offline_packaging_diagnostic"]["envelope"]["valid"])
            self.assertEqual(row["original_release_status"], "abstain")
        report = diagnose_report(fixture({"type": "json_object", "content": advice(), "other": "keep"}))
        self.assertEqual(report["cases"][0]["offline_packaging_diagnostic"]["transformations"], [])

    def test_absent_abstain_invalid_and_empty_never_exact_pass(self):
        for candidate in (None, {"kind": "abstain", "reason": "insufficient_evidence"}, [],
                          {"kind": []}, advice(finding_ids=[], check_ids=[]), advice(finding_ids=["f1", "f2", "f2"])):
            report = diagnose_report(fixture(candidate))
            self.assertEqual(report["summary"]["original"]["findings"]["exact_sets"], 0)
            self.assertEqual(report["summary"]["original"]["cases"], 1)

    def test_guards_excluded_from_content_denominator(self):
        report = diagnose_report(fixture(None, expected_status="abstain", reason="stale"))
        self.assertEqual(report["summary"]["original"]["cases"], 0)
        self.assertIsNone(report["summary"]["original"]["findings"]["micro_recall"])
        self.assertFalse(report["cases"][0]["original"]["content"]["checks"]["exact_set"])

    def test_later_failed_call_does_not_reuse_old_candidate(self):
        report = diagnose_report(fixture(advice(), later_call=True))
        self.assertEqual(report["candidate_states"], {"unparsed_later_provider_call": 1})
        self.assertEqual(report["summary"]["original"]["findings"]["exact_sets"], 0)

    def test_tampering_head_payload_and_report_outcome_rejected(self):
        for mutation in (lambda r: r["evidence"]["events"][0]["payload"].update(kind="modified"),
                         lambda r: r["evidence"]["anchor"].update(head="0" * 64),
                         lambda r: r["evidence"]["events"].pop(0),
                         lambda r: r["cases"][0]["actual"].update(reason="supported"),
                         lambda r: r["cases"].append(copy.deepcopy(r["cases"][0]))):
            report = fixture(advice())
            mutation(report)
            with self.assertRaises(DiagnosticError):
                diagnose_report(report)

    def test_invalid_labels_fail_and_valid_label_changes_are_hashed(self):
        report = fixture(advice())
        before = diagnose_report(report)["expected_labels_sha256"]
        report["cases"][0]["expected"]["findings"] = ["different"]
        self.assertNotEqual(before, diagnose_report(report)["expected_labels_sha256"])
        report["cases"][0]["expected"]["findings"] = []
        with self.assertRaises(DiagnosticError):
            diagnose_report(report)

    def test_file_hash_no_overwrite_strict_json_and_real_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp) / "source.json", Path(temp) / "diagnostic.json"
            source.write_text(json.dumps(fixture(advice())))
            before = source.read_bytes()
            completed = subprocess.run([sys.executable, str(ROOT / "scripts/diagnose_receipts.py"), str(source), "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            saved = json.loads(output.read_text())
            self.assertEqual(saved["input"]["sha256"], hashlib.sha256(before).hexdigest())
            self.assertEqual(source.read_bytes(), before)
            prior = output.read_bytes()
            with self.assertRaises(FileExistsError):
                diagnose_file(source, output)
            self.assertEqual(output.read_bytes(), prior)
            for raw in ('{"cases": [], "cases": []}', '{"cases": NaN}'):
                source.write_text(raw)
                with self.assertRaises(DiagnosticError):
                    diagnose_file(source, Path(temp) / "bad.json")
                self.assertFalse((Path(temp) / "bad.json").exists())

    def test_saved_model_and_negative_control_receipts(self):
        root = ROOT / "receipts/v0.5/deepseek-live-network"
        cloud = diagnose_report(json.loads((root / "cloud-model.json").read_text()))
        summary = cloud["summary"]["offline_packaging_diagnostic"]
        self.assertEqual(summary["findings"]["exact_sets"], 5)
        self.assertEqual(summary["findings"]["micro_recall"], 1)
        self.assertEqual(summary["checks"]["exact_sets"], 0)
        self.assertEqual(summary["checks"]["micro_recall"], 1)
        refusal = diagnose_report(json.loads((root / "always-refuse.json").read_text()))
        self.assertEqual(refusal["summary"]["original"]["findings"]["exact_sets"], 0)
        baseline = diagnose_report(json.loads((root / "baseline.json").read_text()))
        self.assertEqual(baseline["summary"]["original"]["findings"]["exact_sets"], 10)


if __name__ == "__main__":
    unittest.main()
