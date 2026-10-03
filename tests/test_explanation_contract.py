import unittest
from pathlib import Path

from explanation_packets import packet, quality_abstain_observation
from moa.explanation.contract import (ELIGIBLE_ABSTAIN_REASONS, abstention_fits, candidate_view, case_hash, free_text_items,
                                      git_blob_id, kernel_of, resolve_ref)
from moa.knowledge import CHECKS, FINDINGS

ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_git_blob_id_matches_the_case_freeze_pin_for_the_catalog(self):
        self.assertEqual(git_blob_id((ROOT / "moa/knowledge.py").read_bytes()), "5f60b604d5a52ffeaee827d8566301273f6fe919")

    def test_kernel_of_keeps_ids_and_refs_in_kernel_order(self):
        result = {"status": "advisory", "reason": "supported", "findings": [{"id": "b", "text": "B"}, {"id": "a", "text": "A"}],
                  "checks": [{"id": "c", "text": "C"}], "evidence": [{"ref": "policy:lab-v2", "value": {}}]}
        self.assertEqual(kernel_of(result), {"status": "advisory", "reason": "supported", "findings": ["b", "a"],
                                             "checks": ["c"], "evidence": ["policy:lab-v2"]})

    def test_candidate_view_hides_the_label_and_is_a_copy(self):
        case = packet(label="abstention_accepted")
        view = candidate_view(case)
        self.assertEqual(set(view), {"task_id", "observation", "kernel", "excerpts", "catalog"})
        self.assertEqual(view["catalog"]["findings"], {key: FINDINGS[key] for key in case["kernel"]["findings"]})
        self.assertEqual(view["catalog"]["checks"], {key: CHECKS[key] for key in case["kernel"]["checks"]})
        view["kernel"]["findings"].append("mutated")
        self.assertNotIn("mutated", case["kernel"]["findings"])

    def test_kernel_refs(self):
        case = packet()
        for ref, expected in (("kernel:reactor_warming", True), ("kernel:inspect_alarm_context", True),
                              ("kernel:history:TIC201", True), ("kernel:policy:lab-v2", True), ("kernel:status", True),
                              ("kernel:reason", True), ("kernel:reactor_cooling", False), ("kernel:", False),
                              ("kernel", False), ("nonsense:x", False), (7, False)):
            with self.subTest(ref=ref):
                self.assertEqual(resolve_ref(ref, case), expected)

    def test_withheld_kernel_cites_only_status_and_reason(self):
        case = packet(observation=quality_abstain_observation(), label="abstention_accepted")
        self.assertEqual(case["kernel"]["status"], "abstain")
        self.assertTrue(resolve_ref("kernel:status", case))
        self.assertTrue(resolve_ref("kernel:reason", case))
        self.assertFalse(resolve_ref("kernel:policy:lab-v2", case))
        self.assertFalse(resolve_ref("kernel:snapshot:alarms", case))

    def test_observation_pointers_resolve_only_to_scalar_leaves(self):
        case = packet()
        for ref, expected in (("observation:/history/samples/0/values/TIC201", True), ("observation:/captured_at", True),
                              ("observation:/history/samples/0", False), ("observation:/tags", False), ("observation:", False),
                              ("observation:/history/samples/01/values/TIC201", False), ("observation:/history/samples/99/values/TIC201", False),
                              ("observation:/history/samples/0/values/NOPE", False), ("observation:/a~2b", False), ("observation:x", False)):
            with self.subTest(ref=ref):
                self.assertEqual(resolve_ref(ref, case), expected)

    def test_null_history_value_resolves_and_missing_key_does_not(self):
        case = packet("history-quality")
        self.assertIsNone(case["observation"]["history"]["samples"][3]["values"]["TIC201"])
        self.assertTrue(resolve_ref("observation:/history/samples/3/values/TIC201", case))
        self.assertFalse(resolve_ref("observation:/history/samples/3/values/TIC999", case))

    def test_excerpt_index_refs(self):
        excerpt = {"source_id": "https://example.org/doc", "locator": "p1", "text": "Text."}
        case = packet(excerpts=[excerpt, dict(excerpt, locator="p2")])
        for ref, expected in (("excerpt:0", True), ("excerpt:1", True), ("excerpt:2", False), ("excerpt:01", False),
                              ("excerpt:+1", False), ("excerpt:-1", False), ("excerpt:١", False), ("excerpt:", False)):
            with self.subTest(ref=ref):
                self.assertEqual(resolve_ref(ref, case), expected)
        self.assertFalse(resolve_ref("excerpt:0", packet()))

    def test_free_text_items_cover_statements_cause_missing_and_needs(self):
        output = {"kind": "explain", "claims": [{"statement": "a", "support": []}],
                  "causes": [{"statement": "b", "status": "unconfirmed", "support": [], "missing": ["c", "d"]}],
                  "missing_evidence": ["e"]}
        self.assertEqual(free_text_items(output), ["a", "b", "c", "d", "e"])
        self.assertEqual(free_text_items({"kind": "abstain", "reason": "kernel_withheld", "missing_evidence": ["x"]}), ["x"])

    def test_abstention_fit_follows_kernel_status(self):
        advisory, withheld = {"status": "advisory"}, {"status": "abstain"}
        withheld_out = {"kind": "abstain", "reason": "kernel_withheld", "missing_evidence": ["x"]}
        other_out = dict(withheld_out, reason="insufficient_observation")
        self.assertTrue(abstention_fits(withheld_out, withheld))
        self.assertFalse(abstention_fits(withheld_out, advisory))
        self.assertTrue(abstention_fits(other_out, advisory))
        self.assertFalse(abstention_fits(other_out, withheld))
        self.assertFalse(abstention_fits(dict(withheld_out, reason="made_up"), advisory))
        self.assertFalse(abstention_fits({"kind": "explain"}, advisory))

    def test_eligible_reason_list_is_exactly_section_1(self):
        self.assertEqual(ELIGIBLE_ABSTAIN_REASONS, {"incomplete", "conflict", "quality", "incoherent", "units", "invalid_number",
                                                    "history_clock", "history_sequence", "history_timing", "history_incomplete",
                                                    "history_quality", "history_mismatch"})


    def test_non_string_reason_never_fits_and_never_raises(self):
        for reason in (["kernel_withheld"], {"a": 1}, 7, None):
            with self.subTest(reason=reason):
                self.assertFalse(abstention_fits({"kind": "abstain", "reason": reason, "missing_evidence": ["x"]}, {"status": "abstain"}))

    def test_huge_indexes_do_not_resolve_and_do_not_raise(self):
        case = packet(excerpts=[{"source_id": "https://example.org/doc", "locator": "p1", "text": "Text."}])
        self.assertFalse(resolve_ref("excerpt:" + "9" * 5000, case))
        self.assertFalse(resolve_ref("observation:/history/samples/" + "9" * 5000 + "/values/TIC201", case))

    def test_case_hash_ignores_the_hidden_label(self):
        case = packet()
        self.assertEqual(case_hash(case), case_hash(dict(case, label="abstention_accepted")))
        self.assertNotEqual(case_hash(case), case_hash(dict(case, task_id="t-other")))


if __name__ == "__main__":
    unittest.main()
