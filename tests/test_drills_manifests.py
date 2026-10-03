import hashlib
import json
import unittest

from moa.drills import MANIFEST_PATH, MANIFEST_V2_PATH, pinned_manifest

V1_SHA256 = "4da8c8d0a2875a6b706798834af46ceece68a381e2401689f40b279b23885b62"
V1_REVISION = "3aad7695b8720b291999ef0903fcab7b7e008f1e"
V2_REVISION = "bfed001fc89d9beaa640b30a7886d5f16f61a31b"


class DrillManifestTests(unittest.TestCase):
    def test_v1_manifest_bytes_are_unchanged(self):
        self.assertEqual(hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), V1_SHA256)

    def test_v2_changes_only_the_cooling_loss_expectation(self):
        v1, v2 = json.loads(MANIFEST_PATH.read_text()), json.loads(MANIFEST_V2_PATH.read_text())
        self.assertEqual(v2["simulator_revision"], V2_REVISION)
        self.assertEqual(v2["derived_from"], {"path": "moa/data/drills-v1.json", "sha256": V1_SHA256, "simulator_revision": V1_REVISION})
        self.assertEqual((v2["seeds"], v2["split"], v2["review_status"]), (v1["seeds"], v1["split"], v1["review_status"]))
        self.assertNotEqual(v2["suite"], v1["suite"])
        self.assertEqual([c["id"] for c in v2["cases"]], [c["id"] for c in v1["cases"]])
        for old, new in zip(v1["cases"], v2["cases"]):
            if old["id"] == "cooling-loss":
                self.assertEqual(new, {"id": "cooling-loss", "status": "abstain", "reason": "quality", "findings": [], "checks": []})
            else:
                self.assertEqual(new, old)

    def test_pinned_manifest_selects_by_simulator_revision(self):
        self.assertEqual(pinned_manifest(V1_REVISION), json.loads(MANIFEST_PATH.read_text()))
        self.assertEqual(pinned_manifest(V2_REVISION), json.loads(MANIFEST_V2_PATH.read_text()))
        with self.assertRaises(ValueError):
            pinned_manifest("0" * 40)


if __name__ == "__main__":
    unittest.main()
