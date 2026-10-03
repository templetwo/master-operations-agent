import json
import unittest
from pathlib import Path

from explanation_packets import ess_snapshot, packet, quality_abstain_observation
from moa import fixtures
from moa.explanation.contract import git_blob_id
from moa.explanation.eligibility import (LEAK_WORDS_PATH, eligibility_problem, leaks, load_leak_words, parse_gate,
                                         supplement_problems, timestamps_ok)

ROOT = Path(__file__).resolve().parents[1]
EXCERPT = {"source_id": "https://example.org/doc", "locator": "p1", "text": "Jacket temperature rises when coolant flow drops."}


class LeakWordListTests(unittest.TestCase):
    def test_word_list_is_derived_from_its_pinned_sources(self):
        record = json.loads(LEAK_WORDS_PATH.read_text())
        self.assertEqual(record["sources"], {path: git_blob_id((ROOT / path).read_bytes()) for path in record["sources"]})
        derived = set(fixtures.SCENARIOS) | set(record["label_words"])
        for path in ("moa/data/drills-v1.json", "moa/data/drills-v2.json"):
            derived |= {case["id"] for case in json.loads((ROOT / path).read_text())["cases"]}
        self.assertEqual(record["words"], sorted(derived))
        self.assertEqual(load_leak_words(), tuple(sorted(derived)))


class ParseGateTests(unittest.TestCase):
    def test_valid_packets_pass(self):
        for case in (packet(), packet(observation=ess_snapshot()), packet(observation=quality_abstain_observation(), label="abstention_accepted")):
            self.assertIsNone(parse_gate(case))

    def test_shape_failures(self):
        base = packet()
        bad = [dict(base, extra=1), {k: v for k, v in base.items() if k != "label"}, dict(base, label="maybe"),
               dict(base, task_id=7), dict(base, kernel=dict(base["kernel"], summary="x")),
               dict(base, kernel=dict(base["kernel"], status=1)),
               dict(base, excerpts=[EXCERPT] * 7), dict(base, excerpts=[dict(EXCERPT, text="x" * 801)]),
               dict(base, excerpts=[dict(EXCERPT, page=1)]), dict(base, observation="text")]
        for case in bad:
            with self.subTest(case=str(case)[:60]):
                self.assertEqual(parse_gate(case), "parse")

    def test_non_finite_observation_numbers(self):
        for value in (float("nan"), float("inf"), 10 ** 400):
            case = packet()
            case["observation"]["tags"][0]["value"] = value
            with self.subTest(value=str(value)[:12]):
                self.assertEqual(parse_gate(case), "parse")

    def test_kernel_with_sentences_is_its_own_category(self):
        case = packet()
        case["kernel"]["findings"] = [{"id": key, "text": "sentence"} for key in case["kernel"]["findings"]]
        self.assertEqual(parse_gate(case), "kernel_sentences")


class EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.words = load_leak_words()

    def test_eligible_packets(self):
        for case in (packet(), packet("trend-recovery"), packet("history-quality"), packet(observation=ess_snapshot()),
                     packet(observation=quality_abstain_observation(), label="abstention_accepted")):
            self.assertIsNone(eligibility_problem(case, self.words))

    def test_demo_profile_and_wrong_schema_are_profile(self):
        self.assertEqual(eligibility_problem(packet("normal"), self.words), "profile")
        case = packet()
        case["observation"]["schema_version"] = "1.0"
        self.assertEqual(eligibility_problem(case, self.words), "profile")

    def test_reasons_outside_section_1_are_ineligible(self):
        for reason in ("stale", "future", "schema", "profile", "scope", "identifier", "timestamp", "malformed", "invalid_json"):
            case = packet(kernel={"status": "abstain", "reason": reason, "findings": [], "checks": [], "evidence": []})
            self.assertEqual(eligibility_problem(case, self.words), "reason", reason)
        self.assertEqual(eligibility_problem(packet(kernel=dict(packet()["kernel"], status="advice")), self.words), "reason")

    def test_timestamp_pattern(self):
        self.assertTrue(timestamps_ok(packet()["observation"]))
        for value in ("2026-10-01T12:00:00.5Z", "2026-10-01T24:00:00Z", "2026-10-01T12:00:00+00:00", "20261001T120000Z"):
            case = packet()
            case["observation"]["captured_at"] = value
            with self.subTest(value=value):
                self.assertEqual(eligibility_problem(case, self.words), "timestamp")
        case = packet()
        case["observation"]["tags"][2]["observed_at"] = "2026-10-01T12:00:00.1234Z"
        self.assertEqual(eligibility_problem(case, self.words), "timestamp")

    def test_leak_check_on_identifiers_matches_whole_token_runs(self):
        for field, value, leaked in (("snapshot_id", "ess-cooling-loss-1727", True), ("snapshot_id", "ess-normal-1727", True),
                                     ("snapshot_id", "9f3bad1e-feed-4c2a-8b1e-0a1b2c3d4e5f", False),
                                     ("snapshot_id", "abnormal-window", False)):
            case = packet()
            case["observation"][field] = value
            with self.subTest(value=value):
                self.assertEqual(leaks(case, self.words), leaked)
        self.assertTrue(leaks(packet(task_id="explanation_required-01"), self.words))
        case = packet()
        case["observation"]["alarms"][0]["id"] = "tt-stale-hi"
        self.assertTrue(leaks(case, self.words))

    def test_leak_check_on_text_ignores_single_ordinary_words(self):
        self.assertFalse(leaks(packet(excerpts=[dict(EXCERPT, text="Normal cooling water flow after recovery.")]), self.words))
        self.assertTrue(leaks(packet(excerpts=[dict(EXCERPT, text="Seen in the bad-quality drill.")]), self.words))
        self.assertTrue(leaks(packet(excerpts=[dict(EXCERPT, locator="cooling-loss notes")]), self.words))
        self.assertEqual(eligibility_problem(packet(excerpts=[dict(EXCERPT, text="label explanation_required")]), self.words), "leak")

    def test_duplicate_excerpt_pair(self):
        case = packet(excerpts=[EXCERPT, dict(EXCERPT, text="Other text.")])
        self.assertEqual(eligibility_problem(case, self.words), "duplicate_excerpt")
        self.assertIsNone(eligibility_problem(packet(excerpts=[EXCERPT, dict(EXCERPT, locator="p2")]), self.words))


class SupplementTests(unittest.TestCase):
    def test_sizing(self):
        many = [packet(task_id=f"t-{i}", excerpts=[dict(EXCERPT, locator=f"p{i}")]) for i in range(13)]
        self.assertEqual(supplement_problems(many[:12]), [])
        self.assertEqual(supplement_problems(many), ["supplement_count"])
        self.assertEqual(supplement_problems([packet(excerpts=[dict(EXCERPT, text="a " * 201)])]), ["supplement_words"])


if __name__ == "__main__":
    unittest.main()
