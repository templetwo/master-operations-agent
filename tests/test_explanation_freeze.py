"""Stage 0: pins captured before the explanation build changed anything."""
import hashlib
import unittest
from datetime import datetime, timezone
from pathlib import Path

from moa import fixtures
from moa.engine import Agent
from moa.evidence import EvidenceStore
from moa.providers import Baseline

ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
CASE_FREEZE_BLOBS = {
    "moa/knowledge.py": "5f60b604d5a52ffeaee827d8566301273f6fe919",
    "moa/contracts.py": "e0cc78fab60983eca57cc2996afe9885649c8f7a",
    "moa/engine.py": "ab757b25981d04682052046f24b377b594205db4",
    "moa/providers.py": "572aaa54d6a27992d3aaa9ffbe960d755effa2dc",
    "moa/evidence.py": "79cf6c1a0c51d3a166eb5743655236144d96384a",
}
SPECS = {
    "docs/explanation-task-v1.md": "75ab1a26444074927d9f49a34334217ced433d38fcab44281e385599105d5581",
    "docs/explanation-task-v1.1.md": "020699afd7be8d35a424e3df34339172735c0f196bd0e437a8da34d69b163dae",
}
ADV = ("advisory", "supported")
WINDOW_REFS = ["snapshot:alarms", "policy:lab-v2", "history:TIC201", "history:TIC202", "history:FIC102", "history:LIC101", "history:TIC202.OP"]
GOLDEN = {
    "normal": (*ADV, ["no_reported_alarms"], ["continue_observation"], ["snapshot:alarms", "policy:lab-v2"]),
    "cooling": (*ADV, ["reported_alarms", "cooling_mismatch"], ["review_cooling_evidence", "compare_independent_measurement", "inspect_alarm_context"], ["snapshot:alarms", "policy:lab-v2", "tag:TT101", "tag:FT102"]),
    "stale": ("abstain", "stale", [], [], []),
    "bad-quality": ("abstain", "quality", [], [], []),
    "missing": ("abstain", "incomplete", [], [], []),
    "conflict": ("abstain", "conflict", [], [], []),
    "partial": ("abstain", "incomplete", [], [], []),
    "injection": (*ADV, ["reported_alarms", "cooling_mismatch"], ["review_cooling_evidence", "compare_independent_measurement", "inspect_alarm_context"], ["snapshot:alarms", "policy:lab-v2", "tag:TT101", "tag:FT102"]),
    "trend-cooling": (*ADV, ["reported_alarms", "reactor_warming", "jacket_warming", "coolant_output_high", "cooling_path_unconfirmed", "cause_unresolved"], ["inspect_alarm_context", "compare_independent_measurement", "review_cooling_evidence"], WINDOW_REFS),
    "trend-recovery": (*ADV, ["reported_alarms", "reactor_cooling", "coolant_output_high", "cause_unresolved"], ["inspect_alarm_context", "compare_independent_measurement", "monitor_thermal_recovery"], WINDOW_REFS),
    "history-gap": ("abstain", "history_sequence", [], [], []),
    "history-quality": (*ADV, ["reported_alarms", "history_quality_gap", "cause_unresolved"], ["inspect_alarm_context", "compare_independent_measurement", "capture_clean_window"], WINDOW_REFS),
}


def blob(path):
    data = (ROOT / path).read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


class ExplanationFreezeTests(unittest.TestCase):
    def test_modules_pinned_by_the_existing_case_freeze_are_unchanged(self):
        self.assertEqual({path: blob(path) for path in CASE_FREEZE_BLOBS}, CASE_FREEZE_BLOBS)

    def test_specs_are_the_frozen_and_adopted_bytes(self):
        self.assertEqual({path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SPECS}, SPECS)

    def test_baseline_kernels_on_public_fixtures_match_the_measured_golden(self):
        store = EvidenceStore(":memory:")
        try:
            for name, expected in GOLDEN.items():
                with self.subTest(name=name):
                    result = Agent(store, Baseline(), clock=lambda: T0).assess(fixtures.fixture(name, now=T0))
                    actual = (result["status"], result["reason"], [f["id"] for f in result["findings"]],
                              [c["id"] for c in result["checks"]], [e["ref"] for e in result["evidence"]])
                    self.assertEqual(actual, expected)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
