import copy
import platform
import unittest
from pathlib import Path
from unittest.mock import patch

from explanation_packets import ess_snapshot, packet, quality_abstain_observation
from moa.explanation.evaluate import Aborted, call_once, evaluate
from moa.explanation.preflight import preflight
from moa.explanation.template import template

FREEZE = {"prompt_sha256": "p" * 64, "model_id": "toy", "model_digest": "d" * 64, "decoding_sha256": "s" * 64, "schema_sha256": "o" * 64}


def manifest(**changes):
    base = {"catalog_commit": "68cb08c", "manifest_sha256": "m" * 64, "review_sha256": "r" * 64, "grid_sha256": "g" * 64,
            "validation_clocks": {}, "author_python": "3.10.12"}
    return dict(base, **changes)


def good_packets():
    return [packet(task_id="t-a"), packet(task_id="t-b", observation=ess_snapshot()),
            packet(task_id="t-c", observation=quality_abstain_observation(), label="abstention_accepted")]


class CallOnceTests(unittest.TestCase):
    def test_failed_attempts(self):
        def boom(view):
            raise RuntimeError("secret")
        for candidate, failure in ((boom, "exception"), (lambda v: {"kind": "explain", "x": float("nan")}, "non_json"),
                                   (lambda v: {"kind": {1, 2}}, "non_json"), (lambda v: [1], "non_object")):
            with self.subTest(failure=failure):
                self.assertEqual(call_once(candidate, {"k": 1}), (None, failure))

    def test_candidate_gets_a_copy(self):
        view = {"kernel": {"findings": ["a"]}}
        call_once(lambda v: v["kernel"]["findings"].append("b") or {"kind": "abstain"}, view)
        self.assertEqual(view["kernel"]["findings"], ["a"])


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        self.packets = good_packets()
        self.recorded = preflight(self.packets, manifest())

    def test_deterministic_run(self):
        run = evaluate(self.packets, manifest(), self.recorded)
        rows = run["private"]["rows"]
        self.assertEqual(len(rows), 6)
        self.assertEqual({row["candidate"] for row in rows}, {"template", "always-abstain"})
        self.assertTrue(all(row["failure"] is None and row["mechanical"]["problems"] == [] for row in rows))
        self.assertTrue(all(row["mechanical"]["heading"] == "mechanical check (not a reviewer verdict)" for row in rows))
        withheld_template = [r for r in rows if r["candidate"] == "template" and r["kernel_status"] == "abstain"]
        self.assertTrue(withheld_template[0]["abstention_fits"])
        record = run["public"]
        self.assertEqual(record["spec_frozen_against_sha256"], "75ab1a26444074927d9f49a34334217ced433d38fcab44281e385599105d5581")
        self.assertEqual(record["spec_scored_under_sha256"], "020699afd7be8d35a424e3df34339172735c0f196bd0e437a8da34d69b163dae")
        self.assertEqual(record["blobs"]["moa/knowledge.py"], "5f60b604d5a52ffeaee827d8566301273f6fe919")
        self.assertEqual(len(record["evaluator_source_sha256"]), 64)
        self.assertIsNone(record["model_freeze"])

    def test_refusals_before_any_candidate(self):
        bad = copy.deepcopy(self.recorded)
        bad["public"]["runnable"] = False
        with self.assertRaises(Aborted) as caught:
            evaluate(self.packets, manifest(), bad)
        self.assertEqual(caught.exception.code, "preflight")
        with self.assertRaises(Aborted) as caught:
            evaluate(self.packets, manifest(grid_sha256=None), self.recorded)
        self.assertEqual(caught.exception.code, "grid")
        shifted = copy.deepcopy(self.recorded)
        shifted["public"]["valid_set_sha256"] = "0" * 64
        with self.assertRaises(Aborted) as caught:
            evaluate(self.packets, manifest(), shifted)
        self.assertEqual(caught.exception.code, "valid_set")
        with self.assertRaises(Aborted) as caught:
            evaluate(self.packets, manifest(), self.recorded, model=template)
        self.assertEqual(caught.exception.code, "model_freeze")

    def test_model_failures_do_not_stop_the_run_and_never_see_the_label(self):
        seen = []

        def model(view):
            seen.append(sorted(view))
            view["kernel"]["findings"].append("mutated")
            raise RuntimeError("boom")
        run = evaluate(self.packets, manifest(), self.recorded, model=model, model_freeze=FREEZE)
        rows = run["private"]["rows"]
        self.assertEqual(len(rows), 9)
        self.assertEqual([r["failure"] for r in rows if r["candidate"] == "model"], ["exception"] * 3)
        self.assertTrue(all(r["failure"] is None for r in rows if r["candidate"] != "model"))
        self.assertTrue(all("label" not in keys for keys in seen))
        self.assertEqual(self.packets, good_packets())
        self.assertEqual(run["public"]["model_freeze"], FREEZE)


class EvaluateHardeningTests(unittest.TestCase):
    def setUp(self):
        self.packets = good_packets()
        self.recorded = preflight(self.packets, manifest())

    def test_malformed_model_output_is_a_problem_not_a_crash(self):
        run = evaluate(self.packets, manifest(), self.recorded,
                       model=lambda v: {"kind": "abstain", "reason": {"a": 1}, "missing_evidence": ["a"]}, model_freeze=FREEZE)
        model_rows = [r for r in run["private"]["rows"] if r["candidate"] == "model"]
        self.assertEqual(len(model_rows), 3)
        self.assertTrue(all(r["failure"] is None and r["mechanical"]["problems"] == ["abstain_reason"] and not r["abstention_fits"] for r in model_rows))
        self.assertEqual({r["candidate"]: r["run_mode"] for r in run["private"]["rows"]},
                         {"template": "deterministic template", "always-abstain": "deterministic always-abstain", "model": "model"})

    def test_a_checker_crash_is_recorded_as_malformed(self):
        with patch("moa.explanation.evaluate.output_problems", side_effect=RuntimeError("x")):
            run = evaluate(self.packets, manifest(), self.recorded)
        self.assertTrue(all(r["mechanical"]["problems"] == ["malformed"] for r in run["private"]["rows"]))

    def test_partial_model_freeze_is_refused(self):
        for key in FREEZE:
            with self.subTest(missing=key), self.assertRaises(Aborted) as caught:
                evaluate(self.packets, manifest(), self.recorded, model=template, model_freeze={k: v for k, v in FREEZE.items() if k != key})
            self.assertEqual(caught.exception.code, "model_freeze")

    def test_run_record_carries_every_provenance_field(self):
        from moa.explanation.contract import git_blob_id
        from moa.explanation.evaluate import RECORD_FILES
        root = Path(__file__).resolve().parents[1]
        record = evaluate(self.packets, manifest(), self.recorded)["public"]
        self.assertEqual(set(record), {"spec_frozen_against_sha256", "spec_scored_under_sha256", "manifest_sha256", "grid_sha256",
                                       "valid_set_sha256", "leak_words_sha256", "blobs", "python", "author_python",
                                       "evaluator_source_sha256", "model_freeze"})
        self.assertEqual(record["blobs"], {name: git_blob_id((root / name).read_bytes()) for name in RECORD_FILES})
        self.assertEqual(len(RECORD_FILES), 9)
        self.assertEqual((record["manifest_sha256"], record["grid_sha256"], record["author_python"]), ("m" * 64, "g" * 64, "3.10.12"))
        self.assertEqual(record["valid_set_sha256"], self.recorded["public"]["valid_set_sha256"])
        self.assertEqual(record["leak_words_sha256"], self.recorded["public"]["leak_words_sha256"])
        self.assertEqual(record["python"], platform.python_version())


if __name__ == "__main__":
    unittest.main()
