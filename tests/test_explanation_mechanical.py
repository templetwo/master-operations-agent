import copy
import unittest

from explanation_packets import packet, quality_abstain_observation
from moa.explanation.contract import ELIGIBLE_ABSTAIN_REASONS, candidate_view
from moa.explanation.enumerate import reachable_window_outcomes
from moa.explanation.mechanical import HEADING, output_problems
from moa.explanation.template import always_abstain, template
from moa.knowledge import CHECKS, FINDINGS


def kernel_packet(status, reason, findings=(), checks=(), evidence=()):
    return {"task_id": "x", "observation": {}, "excerpts": [], "label": "explanation_required",
            "kernel": {"status": status, "reason": reason, "findings": list(findings), "checks": list(checks), "evidence": list(evidence)}}


def claim(text, *refs):
    return {"statement": text, "support": list(refs) or ["kernel:reported_alarms"]}


def explain(claims, causes=(), needs=("A clean window.",)):
    return {"kind": "explain", "claims": list(claims), "causes": list(causes), "missing_evidence": list(needs)}


class MechanicalTests(unittest.TestCase):
    def setUp(self):
        self.case = packet("trend-cooling")

    def test_heading_text(self):
        self.assertEqual(HEADING, "mechanical check (not a reviewer verdict)")

    def test_template_and_control_pass_on_every_reachable_window(self):
        for findings, checks in reachable_window_outcomes():
            case = kernel_packet("advisory", "supported", findings, checks, ["snapshot:alarms", "policy:lab-v2"])
            self.assertEqual(output_problems(template(candidate_view(case)), case), [], (findings, checks))
            self.assertEqual(output_problems(always_abstain(candidate_view(case)), case), [])

    def test_template_passes_on_every_eligible_withheld_kernel(self):
        for reason in sorted(ELIGIBLE_ABSTAIN_REASONS):
            case = kernel_packet("abstain", reason)
            self.assertEqual(output_problems(template(candidate_view(case)), case), [], reason)

    def test_shape_problems(self):
        good = explain([claim("Alarms are reported.")])
        cases = [
            ([], ["not_object"]),
            ({"kind": "summary"}, ["kind"]),
            (dict(good, extra=1), ["fields"]),
            (explain([]), ["claims_count"]),
            (explain([claim("x")] * 13), ["claims_count"]),
            (explain([claim("x")], causes=[{"statement": "c", "status": "unconfirmed", "support": ["kernel:status"], "missing": ["m"]}] * 5), ["causes_count"]),
            (explain([claim("x")], needs=["n"] * 9), ["missing_evidence_count"]),
            (explain([{"statement": "x"}]), ["fields"]),
            (explain([claim("x")], causes=[{"statement": "c", "status": "confirmed", "support": ["kernel:status"], "missing": ["m"]}]), ["status_value"]),
            (explain([claim("x")], causes=[{"statement": "c", "status": "unconfirmed", "support": ["kernel:status"], "missing": []}]), ["missing_count"]),
            (explain([{"statement": 5, "support": ["kernel:status"]}]), ["type"]),
            ({"kind": "abstain", "reason": "bored", "missing_evidence": ["x"]}, ["abstain_reason"]),
            ({"kind": "abstain", "reason": "kernel_withheld", "missing_evidence": []}, ["missing_evidence_count"]),
        ]
        for output, expected in cases:
            with self.subTest(output=str(output)[:80]):
                self.assertEqual(output_problems(output, self.case), expected)

    def test_support_problems(self):
        cases = [
            ([claim("x", "kernel:status", "kernel:reason", "kernel:reported_alarms", "kernel:reactor_warming", "kernel:jacket_warming")], ["support_count"]),
            ([{"statement": "x", "support": []}], ["support_count"]),
            ([claim("x", "kernel:status", "kernel:status")], ["support_repeat"]),
            ([claim("x", "kernel:reactor_cooling")], ["ref_unresolved"]),
            ([claim("x", "kernel:policy:lab-v2")], ["support_universal_only"]),
            ([claim("x", "kernel:policy:lab-v2", "kernel:snapshot:alarms")], ["support_universal_only"]),
            ([claim("x", "kernel:policy:lab-v2", "observation:/captured_at")], []),
        ]
        for claims, expected in cases:
            with self.subTest(claims=claims):
                self.assertEqual(output_problems(explain(claims), self.case), expected)

    def test_missing_evidence_may_be_empty_only_without_open_uncertainty(self):
        self.assertEqual(output_problems(explain([claim("x")], needs=[]), self.case), ["missing_evidence_empty"])
        quiet = kernel_packet("advisory", "supported", ["no_reported_alarms"], ["continue_observation"], ["snapshot:alarms", "policy:lab-v2"])
        self.assertEqual(output_problems(explain([claim("x", "kernel:no_reported_alarms")], needs=[]), quiet), [])
        withheld = packet(observation=quality_abstain_observation())
        self.assertEqual(output_problems(explain([claim("Withheld.", "kernel:status")], needs=[]), withheld), ["missing_evidence_empty"])

    def test_ids_and_sentences_outside_the_kernel(self):
        self.assertEqual(output_problems(explain([claim("See reactor_cooling here.")]), self.case), ["new_id"])
        self.assertEqual(output_problems(explain([claim(FINDINGS["reactor_cooling"])]), self.case), ["foreign_sentence"])
        self.assertEqual(output_problems(explain([claim("x")], needs=[CHECKS["review_feed_balance"]]), self.case), ["foreign_sentence"])
        self.assertEqual(output_problems(explain([claim(FINDINGS["reactor_warming"], "kernel:reactor_warming")]), self.case), [])

    def test_caps_count_code_points(self):
        self.assertEqual(output_problems(explain([claim("\U0001F600" * 240)]), self.case), [])
        self.assertEqual(output_problems(explain([claim("\U0001F600" * 241)]), self.case), ["item_chars"])
        self.assertEqual(output_problems(explain([claim("é" * 210)] * 12), self.case), ["total_chars"])


if __name__ == "__main__":
    unittest.main()
