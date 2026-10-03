import unittest

from explanation_packets import packet, quality_abstain_observation
from moa.explanation.contract import candidate_view
from moa.explanation.template import always_abstain, template
from moa.knowledge import CHECKS, FINDINGS


class TemplateTests(unittest.TestCase):
    def test_advisory_cooling_window(self):
        case = packet("trend-cooling")
        output = template(candidate_view(case))
        self.assertEqual(output["kind"], "explain")
        self.assertEqual([c["statement"] for c in output["claims"]], [FINDINGS[k] for k in case["kernel"]["findings"]])
        self.assertEqual([c["support"] for c in output["claims"]], [["kernel:" + k] for k in case["kernel"]["findings"]])
        self.assertEqual(output["causes"], [{"statement": FINDINGS["cooling_path_unconfirmed"], "status": "unconfirmed",
                                             "support": ["kernel:cooling_path_unconfirmed"],
                                             "missing": ["compare_independent_measurement", "review_cooling_evidence"]}])
        self.assertEqual(output["missing_evidence"], [CHECKS[k] for k in case["kernel"]["checks"]])

    def test_uncertainty_findings_other_than_cooling_are_claims_only(self):
        for name in ("trend-recovery", "history-quality"):
            with self.subTest(name=name):
                self.assertEqual(template(candidate_view(packet(name)))["causes"], [])

    def test_withheld_kernel_gives_the_fixed_abstention(self):
        case = packet(observation=quality_abstain_observation())
        self.assertEqual(template(candidate_view(case)), {
            "kind": "abstain", "reason": "kernel_withheld",
            "missing_evidence": ["An observation that passes the validator check named by kernel reason quality."]})

    def test_template_ignores_excerpts(self):
        excerpt = {"source_id": "https://example.org/doc", "locator": "p1", "text": "Text."}
        self.assertEqual(template(candidate_view(packet(excerpts=[excerpt]))), template(candidate_view(packet())))

    def test_always_abstain_is_constant(self):
        expected = {"kind": "abstain", "reason": "insufficient_observation", "missing_evidence": ["Not assessed."]}
        self.assertEqual(always_abstain(candidate_view(packet())), expected)
        self.assertEqual(always_abstain(candidate_view(packet(observation=quality_abstain_observation()))), expected)


if __name__ == "__main__":
    unittest.main()
