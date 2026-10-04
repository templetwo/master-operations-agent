import hashlib
import json
import unittest

from moa.drills import MANIFEST_PATH, MANIFEST_V2_PATH, MANIFEST_V3_PATH, pinned_manifest

V1_SHA256 = "4da8c8d0a2875a6b706798834af46ceece68a381e2401689f40b279b23885b62"
V1_REVISION = "3aad7695b8720b291999ef0903fcab7b7e008f1e"
V2_REVISION = "bfed001fc89d9beaa640b30a7886d5f16f61a31b"
V2_SHA256 = "165e12c7cdd238d10f590c174b29747c7302a06a33692fa537be7e2f38163438"
V3_REVISION = "adeb18a92de942ed1a60bcf4112430baa071c89d"


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

    def test_v2_manifest_bytes_are_unchanged(self):
        self.assertEqual(hashlib.sha256(MANIFEST_V2_PATH.read_bytes()).hexdigest(), V2_SHA256)

    def test_v3_changes_only_the_restoration_lag_expectation(self):
        v2, v3 = json.loads(MANIFEST_V2_PATH.read_text()), json.loads(MANIFEST_V3_PATH.read_text())
        self.assertEqual(v3["simulator_revision"], V3_REVISION)
        self.assertEqual(v3["derived_from"], {"path": "moa/data/drills-v2.json", "sha256": V2_SHA256, "simulator_revision": V2_REVISION})
        self.assertEqual((v3["seeds"], v3["split"], v3["review_status"]), (v2["seeds"], v2["split"], v2["review_status"]))
        self.assertNotIn(v3["suite"], (v2["suite"], json.loads(MANIFEST_PATH.read_text())["suite"]))
        self.assertEqual([c["id"] for c in v3["cases"]], [c["id"] for c in v2["cases"]])
        for old, new in zip(v2["cases"], v3["cases"]):
            if old["id"] == "restoration-lag":
                self.assertEqual(new, dict(old, findings=["reported_alarms", "cause_unresolved"]))
            else:
                self.assertEqual(new, old)

    def test_pinned_manifest_selects_by_simulator_revision(self):
        self.assertEqual(pinned_manifest(V1_REVISION), json.loads(MANIFEST_PATH.read_text()))
        self.assertEqual(pinned_manifest(V2_REVISION), json.loads(MANIFEST_V2_PATH.read_text()))
        self.assertEqual(pinned_manifest(V3_REVISION), json.loads(MANIFEST_V3_PATH.read_text()))
        with self.assertRaises(ValueError):
            pinned_manifest("0" * 40)


if __name__ == "__main__":
    unittest.main()
