import json
import unittest

from explanation_packets import ess_snapshot, packet, quality_abstain_observation
from moa.explanation.evaluate import evaluate
from moa.explanation.preflight import preflight
from moa.explanation.review import IncompleteReview, public_report, review_sheet, tally
from moa.explanation.template import template
from moa.explanation.contract import case_hash

FREEZE = {"prompt_sha256": "p" * 64, "model_id": "toy", "model_digest": "d" * 64, "decoding_sha256": "s" * 64, "schema_sha256": "o" * 64}
MANIFEST = {"catalog_commit": "68cb08c", "manifest_sha256": "m" * 64, "review_sha256": "r" * 64, "grid_sha256": "g" * 64,
            "validation_clocks": {}, "author_python": "3.10.12"}


def run_with_model():
    packets = [packet(task_id="t-a"), packet(task_id="t-b", observation=ess_snapshot(), label="abstention_accepted"),
               packet(task_id="t-c", observation=quality_abstain_observation(), label="abstention_accepted")]
    return evaluate(packets, MANIFEST, preflight(packets, MANIFEST), model=template, model_freeze=FREEZE)


def all_pass(sheet):
    return {"rows": {row["row_id"]: {**{c: "pass" for c in "123456"}, "abstention": "pass", "note": "ok"} for row in sheet["rows"]},
            "pairs": {pair["case_hash"]: "tie" for pair in sheet["pairs"]}}


class ReviewSheetTests(unittest.TestCase):
    def setUp(self):
        self.run = run_with_model()
        self.sheet, self.key = review_sheet(self.run, "salt-1")

    def test_sheet_is_blind_and_blank(self):
        text = json.dumps(self.sheet)
        for hidden in ("explanation_required", "abstention_accepted", "always-abstain", '"candidate"', '"label"'):
            self.assertNotIn(hidden, text)
        self.assertEqual(len(self.sheet["rows"]), 6)
        self.assertTrue(all(set(row["cells"]) == {"1", "2", "3", "4", "5", "6", "abstention", "note"} for row in self.sheet["rows"]))
        self.assertTrue(all(value is None for row in self.sheet["rows"] for value in row["cells"].values()))
        self.assertTrue(self.sheet["single_reviewer"])
        self.assertEqual(self.sheet["mechanical_heading"], "mechanical check (not a reviewer verdict)")

    def test_pairs_only_for_advisory_cases_with_template_and_model(self):
        self.assertEqual(len(self.sheet["pairs"]), 2)
        self.assertTrue(all(len(pair["rows"]) == 2 and pair["preferred"] is None for pair in self.sheet["pairs"]))

    def test_row_ids_depend_on_salt_and_map_back_through_the_key(self):
        other, other_key = review_sheet(self.run, "salt-2")
        self.assertNotEqual({r["row_id"] for r in self.sheet["rows"]}, {r["row_id"] for r in other["rows"]})
        self.assertEqual({v["candidate"] for v in self.key["rows"].values()}, {"template", "model"})
        self.assertEqual(review_sheet(self.run, "salt-1")[0], self.sheet)


class TallyTests(unittest.TestCase):
    def setUp(self):
        self.run = run_with_model()
        self.sheet, self.key = review_sheet(self.run, "salt-1")

    def test_counts_from_recorded_verdicts(self):
        counted = tally(self.run, self.key, all_pass(self.sheet))
        template_advisory = counted["candidates"]["template"]["advisory"]
        self.assertEqual(template_advisory, {"all_six_on_explanation_required": 1, "explanation_passes": 2,
                                             "abstention_passes": 0, "failed_attempts": 0, "outputs": 2})
        self.assertEqual(counted["candidates"]["template"]["abstain"]["abstention_passes"], 1)
        control = counted["candidates"]["always-abstain"]
        self.assertEqual(sum(bucket["abstention_passes"] + bucket["explanation_passes"] for bucket in control.values()), 0)
        self.assertEqual(counted["preferences"], {"model": 0, "template": 0, "tie": 2})

    def test_failed_reviewer_cells_do_not_count(self):
        verdicts = all_pass(self.sheet)
        for row_id in verdicts["rows"]:
            verdicts["rows"][row_id]["5"] = "fail"
        counted = tally(self.run, self.key, verdicts)
        self.assertEqual(counted["candidates"]["template"]["advisory"]["explanation_passes"], 0)

    def test_missing_or_partial_verdicts_refuse_to_tally(self):
        verdicts = all_pass(self.sheet)
        verdicts["rows"].pop(next(iter(verdicts["rows"])))
        with self.assertRaises(IncompleteReview):
            tally(self.run, self.key, verdicts)
        verdicts = all_pass(self.sheet)
        verdicts["rows"][next(iter(verdicts["rows"]))]["3"] = "maybe"
        with self.assertRaises(IncompleteReview):
            tally(self.run, self.key, verdicts)

    def test_preference_maps_through_the_key_and_must_stay_in_its_case(self):
        verdicts = all_pass(self.sheet)
        pair = self.sheet["pairs"][0]
        model_row = next(r for r in pair["rows"] if self.key["rows"][r]["candidate"] == "model")
        verdicts["pairs"][pair["case_hash"]] = model_row
        self.assertEqual(tally(self.run, self.key, verdicts)["preferences"], {"model": 1, "template": 0, "tie": 1})
        verdicts["pairs"][pair["case_hash"]] = self.sheet["pairs"][1]["rows"][0]
        with self.assertRaises(IncompleteReview):
            tally(self.run, self.key, verdicts)

    def test_public_report_is_an_allowlist(self):
        report = public_report(self.run, tally(self.run, self.key, all_pass(self.sheet)))
        self.assertEqual(set(report), {"schema", "spec_frozen_against_sha256", "spec_scored_under_sha256", "review",
                                       "useful_measure", "run_modes", "record", "counts", "preferences", "limits"})
        self.assertEqual(report["review"], "single-reviewer")
        self.assertEqual(report["useful_measure"], "all-six passes, single-reviewer")
        text = json.dumps(report)
        for row in self.run["private"]["rows"]:
            self.assertNotIn(row["case_hash"], text)
        for task_id in ("t-a", "t-b", "t-c"):
            self.assertNotIn(task_id, text)


def abstain_model(view):
    return {"kind": "abstain", "reason": "insufficient_observation", "missing_evidence": ["x"]}


class HardenedTallyTests(unittest.TestCase):
    def setUp(self):
        self.run = run_with_model()
        self.sheet, self.key = review_sheet(self.run, "salt-1")

    def test_rows_are_shuffled_by_salt_not_by_candidate(self):
        packets = [packet(task_id=f"t-{i}") for i in range(4)]
        run = evaluate(packets, MANIFEST, preflight(packets, MANIFEST), model=template, model_freeze=FREEZE)
        first = set()
        for salt in (f"s{i}" for i in range(12)):
            sheet, key = review_sheet(run, salt)
            for pair in sheet["pairs"]:
                first.add(key["rows"][pair["rows"][0]]["candidate"])
        self.assertEqual(first, {"template", "model"})

    def test_abstention_cell_is_required_on_abstain_rows(self):
        verdicts = all_pass(self.sheet)
        for row in self.sheet["rows"]:
            if row["output"]["kind"] == "abstain":
                verdicts["rows"][row["row_id"]]["abstention"] = None
        with self.assertRaises(IncompleteReview):
            tally(self.run, self.key, verdicts)

    def test_abstention_count_needs_a_pass_cell_a_fitting_reason_and_the_label(self):
        verdicts = all_pass(self.sheet)
        for row in self.sheet["rows"]:
            if row["output"]["kind"] == "abstain":
                verdicts["rows"][row["row_id"]]["abstention"] = "fail"
        self.assertEqual(tally(self.run, self.key, verdicts)["candidates"]["template"]["abstain"]["abstention_passes"], 0)
        packets = [packet(task_id="t-c", observation=quality_abstain_observation(), label="explanation_required")]
        run = evaluate(packets, MANIFEST, preflight(packets, MANIFEST), model=abstain_model, model_freeze=FREEZE)
        sheet, key = review_sheet(run, "salt-1")
        counted = tally(run, key, all_pass(sheet))
        self.assertEqual(counted["candidates"]["template"]["abstain"]["abstention_passes"], 0)
        packets = [packet(task_id="t-c", observation=quality_abstain_observation(), label="abstention_accepted")]
        run = evaluate(packets, MANIFEST, preflight(packets, MANIFEST), model=abstain_model, model_freeze=FREEZE)
        sheet, key = review_sheet(run, "salt-1")
        counted = tally(run, key, all_pass(sheet))
        self.assertEqual(counted["candidates"]["model"]["abstain"]["abstention_passes"], 0)
        self.assertEqual(counted["candidates"]["template"]["abstain"]["abstention_passes"], 1)

    def test_failed_attempts_are_counted(self):
        def boom(view):
            raise RuntimeError("x")
        packets = [packet(task_id="t-a")]
        run = evaluate(packets, MANIFEST, preflight(packets, MANIFEST), model=boom, model_freeze=FREEZE)
        sheet, key = review_sheet(run, "salt-1")
        counted = tally(run, key, all_pass(sheet))
        self.assertEqual(counted["candidates"]["model"]["advisory"]["failed_attempts"], 1)
        self.assertEqual(counted["candidates"]["model"]["advisory"]["explanation_passes"], 0)

    def test_pairs_must_match_the_sheet_exactly(self):
        for change in ({}, "unknown", "extra", "non_pair"):
            verdicts = all_pass(self.sheet)
            if change == {}:
                verdicts["pairs"] = {}
            elif change == "unknown":
                verdicts["pairs"] = {"deadbeef": "tie", **{k: v for k, v in list(verdicts["pairs"].items())[1:]}}
            elif change == "extra":
                verdicts["pairs"]["deadbeef"] = "tie"
            else:
                withheld = next(h for h, p in self.run["private"]["packets"].items() if p["kernel"]["status"] == "abstain")
                verdicts["pairs"][withheld] = "tie"
            with self.subTest(change=str(change)), self.assertRaises(IncompleteReview):
                tally(self.run, self.key, verdicts)

    def test_malformed_verdict_shapes_raise_incomplete_review(self):
        good = all_pass(self.sheet)
        row_id = next(iter(good["rows"]))
        bad_values = [dict(good, rows=[]), dict(good, pairs=[]), {"pairs": good["pairs"]}, None,
                      dict(good, rows={**good["rows"], row_id: dict(good["rows"][row_id], **{"2": ["pass"]})}),
                      dict(good, rows={**good["rows"], row_id: "pass"})]
        for verdicts in bad_values:
            with self.subTest(verdicts=str(verdicts)[:60]), self.assertRaises(IncompleteReview):
                tally(self.run, self.key, verdicts)

    def test_sheet_case_hashes_do_not_reveal_the_label(self):
        for case, view in self.sheet["cases"].items():
            original = self.run["private"]["packets"][case]
            for label in ("explanation_required", "abstention_accepted"):
                self.assertEqual(case_hash(dict(original, label=label)), case)


if __name__ == "__main__":
    unittest.main()
