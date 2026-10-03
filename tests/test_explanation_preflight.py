import json
import unittest
from datetime import timedelta

from explanation_packets import T0, ess_snapshot, kernel_for, packet, quality_abstain_observation
from moa.contracts import digest
from moa.explanation.preflight import Refused, freeze_check, preflight


def manifest(**changes):
    base = {"catalog_commit": "68cb08c", "manifest_sha256": "m" * 64, "review_sha256": "r" * 64, "grid_sha256": "g" * 64,
            "validation_clocks": {}, "author_python": "3.10.12"}
    return dict(base, **changes)


def good_packets():
    return [packet(task_id="t-a"), packet(task_id="t-b", observation=ess_snapshot()),
            packet(task_id="t-c", observation=quality_abstain_observation(), label="abstention_accepted")]


class FreezeCheckTests(unittest.TestCase):
    def test_refusals(self):
        for broken, code in ((dict(manifest(), validation_clocks=None), "manifest"),
                             ({k: v for k, v in manifest().items() if k != "grid_sha256"}, "manifest"),
                             (manifest(review_sha256=None), "review"),
                             (manifest(catalog_commit="0000000"), "catalog"),
                             (manifest(catalog_commit="68cb08c; rm -rf /"), "catalog")):
            with self.subTest(code=code), self.assertRaises(Refused) as caught:
                freeze_check(broken)
            self.assertEqual(caught.exception.code, code)

    def test_existing_freeze_commit_matches_the_catalog_pin(self):
        self.assertEqual(freeze_check(manifest()), "5f60b604d5a52ffeaee827d8566301273f6fe919")


class PreflightTests(unittest.TestCase):
    def test_all_valid_packets_are_runnable(self):
        result = preflight(good_packets(), manifest())
        public = result["public"]
        self.assertTrue(public["runnable"])
        self.assertEqual((public["packets"], public["valid_count"], public["invalid_counts"], public["package_problems"]), (3, 3, {}, []))
        self.assertEqual(result["private"]["valid_task_ids"], ["t-a", "t-b", "t-c"])
        self.assertEqual(public["valid_set_sha256"], digest(["t-a", "t-b", "t-c"]))
        for task_id in ("t-a", "t-b", "t-c"):
            self.assertNotIn(task_id, json.dumps(public))

    def test_each_invalid_category_is_counted_not_dropped(self):
        tampered = packet(task_id="t-m")
        tampered["kernel"]["findings"] = tampered["kernel"]["findings"][:-1]
        stale = packet(task_id="t-s", kernel=kernel_for(packet()["observation"], when=T0 + timedelta(seconds=120)))
        with_sentences = packet(task_id="t-k")
        with_sentences["kernel"]["findings"] = [{"id": key, "text": "x"} for key in with_sentences["kernel"]["findings"]]
        packets = good_packets() + [tampered, stale, with_sentences, packet(task_id="t-a"), {"task_id": "t-z"}]
        public = preflight(packets, manifest())["public"]
        self.assertFalse(public["runnable"])
        self.assertEqual(public["valid_count"], 3)
        self.assertEqual(public["invalid_counts"], {"duplicate_task_id": 1, "kernel_mismatch": 1, "kernel_sentences": 1,
                                                    "parse": 1, "reason": 1})

    def test_manifest_clock_drives_the_rerun(self):
        author_clock = T0 + timedelta(seconds=30)
        case = packet(task_id="t-c30", kernel=kernel_for(packet()["observation"], when=author_clock))
        self.assertTrue(preflight([case], manifest(validation_clocks={"t-c30": "2026-10-01T12:00:30.000Z"}))["public"]["runnable"])
        late = preflight([case], manifest(validation_clocks={"t-c30": "2026-10-01T12:02:00.000Z"}))["public"]
        self.assertEqual(late["invalid_counts"], {"kernel_mismatch": 1})
        broken = preflight([case], manifest(validation_clocks={"t-c30": "noon"}))["public"]
        self.assertEqual(broken["invalid_counts"], {"clock": 1})

    def test_supplement_problem_blocks_the_run(self):
        excerpt = {"source_id": "https://example.org/doc", "locator": "p1", "text": "a " * 201}
        public = preflight([packet(excerpts=[excerpt])], manifest())["public"]
        self.assertEqual(public["package_problems"], ["supplement_words"])
        self.assertFalse(public["runnable"])

    def test_empty_package_is_not_runnable(self):
        self.assertFalse(preflight([], manifest())["public"]["runnable"])


if __name__ == "__main__":
    unittest.main()
