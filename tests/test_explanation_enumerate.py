import unittest

from explanation_packets import kernel_for
from moa.explanation.contract import candidate_view, free_text_items
from moa.explanation.enumerate import reachable_window_outcomes, window_observation
from moa.explanation.template import template


def advisory_view(findings, checks):
    kernel = {"status": "advisory", "reason": "supported", "findings": list(findings), "checks": list(checks),
              "evidence": ["snapshot:alarms", "policy:lab-v2"]}
    return candidate_view({"task_id": "x", "observation": {}, "kernel": kernel, "excerpts": [], "label": "explanation_required"})


class EnumerateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outcomes = reachable_window_outcomes()

    def test_reachable_space_matches_the_spec_measurement(self):
        self.assertEqual(len(self.outcomes), 202)
        self.assertEqual(max(len(f) for f, _ in self.outcomes), 9)
        self.assertEqual(max(len(f) + len(c) for f, c in self.outcomes), 14)

    def test_nine_finding_witness_holds_through_the_validator(self):
        series = {"TIC201": [0, 0, 5, 2], "TIC202": [10, 10, 10, 13], "FIC102": [20, 20, 20, 25],
                  "LIC101": [30, 30, 30, 33], "TIC202.OP": [50, 50, 50, 95]}
        kernel = kernel_for(window_observation(series))
        self.assertEqual(kernel["status"], "advisory")
        self.assertEqual(len(kernel["findings"]), 9)

    def test_template_maxima_are_the_section_4_figures(self):
        outputs = [template(advisory_view(f, c)) for f, c in self.outcomes]
        self.assertEqual(max(len(o["claims"]) for o in outputs), 9)
        self.assertEqual(max(len(o["causes"]) for o in outputs), 1)
        self.assertEqual(max(len(o["missing_evidence"]) for o in outputs), 5)
        self.assertEqual(max(len(t) for o in outputs for t in free_text_items(o)), 224)
        self.assertEqual(max(sum(map(len, free_text_items(o))) for o in outputs), 1826)


if __name__ == "__main__":
    unittest.main()
