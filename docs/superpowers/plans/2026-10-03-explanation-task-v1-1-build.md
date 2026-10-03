# Explanation Task v1.1 Evaluator Implementation Plan

> **Status:** executed inline on 2026-10-03 (commits `42f57ae`..`d7a6ccb`, merged in `713454f`). The checkboxes below were not maintained. This file is kept as the build record.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the adopted explanation-task v1.1 evaluator as a library: shared contract, deterministic template and control, mechanical checks, packet gates, preflight, evaluation run, blind review sheet, tally and a counts-only public report. No model is called and no private case is read.

**Architecture:** A new package `moa/explanation/` with one responsibility per file. `contract.py` is the shared contract: constants, reference resolution, the candidate view and free-text rules. Every other module imports its caps and code lists from it and restates none of them. Preflight gates every packet, reruns the deterministic baseline at a fixed clock, and returns counts and hashes before any candidate runs. The evaluator calls each candidate once per valid packet. The review module produces a blank, shuffled sheet for Anthony and tallies only his recorded verdicts. Nothing reads files outside the repository, and nothing prints. Loading the real case package is a later plan, once its layout is supplied by its author.

**Tech Stack:** Python 3.10+ standard library and `unittest`. Existing `moa.contracts`, `moa.engine.Agent`, `moa.providers.Baseline`, `moa.evidence.EvidenceStore`, `moa.knowledge` and `moa.fixtures`. No new dependencies.

**Spec:** `docs/explanation-task-v1.1.md`, adopted per `docs/explanation-task-v1.1-adoption.md` (sha256 `020699afd7be8d35a424e3df34339172735c0f196bd0e437a8da34d69b163dae`, all ten decisions as recommended). It revises `docs/explanation-task-v1.md` (sha256 `75ab1a26444074927d9f49a34334217ced433d38fcab44281e385599105d5581`), which stays frozen.

## Global Constraints

**Repository rules (AGENTS.md):**

- Synthetic research lane only. Add no tool to the advisor allowlist, and no cloud fallback, model download, credential discovery, shell tool, arbitrary HTTP or simulator write.
- No unsupported benchmark, safety, readiness or certification claim. Plain language.

**Frozen inputs:**

- `docs/explanation-task-v1.md`, `docs/explanation-task-v1.1.md`, `moa/knowledge.py`, `moa/contracts.py`, `moa/engine.py`, `moa/providers.py` and `moa/evidence.py` are not edited by this plan. The existing case freeze pins the five modules at blob `5f60b604` / `e0cc78fa` / `ab757b25` / `572aaa54` / `79cf6c1a`.

**Exposure and privacy:**

- Never read anything under `~/.moa`. Tests use public fixtures and toy packets only.
- No module prints. Error messages are fixed strings with no packet content.
- No builder edits `moa/cli.py`.

**Caps, from section 4 and Decision 2:**

- 12 claims, 4 causes, 8 `missing` items per cause, 8 `missing_evidence` items, and 1 to 4 refs per support list.
- 240 code points per free-text item, 2400 in total.
- At most 6 excerpts per packet, each at most 800 characters.
- The supplement holds at most 12 excerpts, each at most 200 words.

**Eligibility, from section 1:**

- **Eligible abstain reasons:** `incomplete`, `conflict`, `quality`, `incoherent`, `units`, `invalid_number`, `history_clock`, `history_sequence`, `history_timing`, `history_incomplete`, `history_quality`, `history_mismatch`.
- **Packet profiles:** `ess-u1-window-v1` with schema `1.1`, or `ess-u1-v1` with schema `1.0` or `1.3`.
- **Timestamps:** `[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{3}|\.[0-9]{6})?Z`, full match, hour 00 to 23. Checked on `captured_at` and each `tags[].observed_at`, the only timestamps the validator reads.

**Review rules, from sections 7 and 8:**

- Mechanical results are reported under the heading `mechanical check (not a reviewer verdict)`.
- Every report is labelled `single-reviewer`. The useful measure is named `all-six passes, single-reviewer`.

**Test commands:**

- Explanation tests: `python3 -m unittest discover -s tests -p 'test_explanation_*.py' -v`
- Full suite: `python3 -m unittest discover -s tests`

## Review Focus

The spec implies these inputs, but no task's main path exercises them. Each has a pinning test in the task that owns the code.

1. **A case package that recorded catalog sentences instead of ids in `kernel`.** Preflight must count it as `kernel_sentences` and keep going, not crash and not compare. Pinned in Task 7.
2. **Two packets sharing one `task_id`.** It must be counted as `duplicate_task_id` and make the run not runnable, never silently merged. Pinned in Task 7.
3. **A candidate returning something that is not finite JSON** (a `set`, `NaN`, a list). It must be recorded as a failed attempt (`non_json` or `non_object`) while the other candidates still run. Pinned in Task 8.
4. **A citation of a null history value** (a sample whose quality is not good). It must resolve, while a pointer to a missing key must not. Pinned in Task 2.
5. **Free text with non-ASCII characters.** It is counted by code points: 240 emoji pass and 241 fail. Pinned in Task 5.

---

### Task 1: Stage 0 freeze of current behaviour

**Files:**
- Create: `tests/test_explanation_freeze.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: the pins every later task must keep green.

- [ ] **Step 1: Write the freeze test with the measured values**

```python
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
```

- [ ] **Step 2: Run it**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_freeze.py' -v`
Expected: `Ran 3 tests` … `OK`. These values were measured on 2026-10-03 at `3d79ece`, before any build change. A freeze characterizes existing behaviour, so it passes first.

- [ ] **Step 3: Prove the golden test can fail**

Temporarily change `"stale": ("abstain", "stale", ...)` to `("abstain", "quality", ...)`, then run the same command.
Expected: `FAIL: test_baseline_kernels_on_public_fixtures_match_the_measured_golden (name='stale')`.
Then restore the line and rerun. Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_explanation_freeze.py
git commit -m "test(explanation): stage 0 freeze of pinned modules, specs and fixture kernels"
```

---

### Task 2: Shared contract module

**Files:**
- Create: `moa/explanation/__init__.py`
- Create: `moa/explanation/contract.py`
- Create: `tests/explanation_packets.py` (public toy packet helpers, no private content)
- Test: `tests/test_explanation_contract.py`

**Interfaces:**
- Consumes: `moa.knowledge.FINDINGS`, `moa.knowledge.CHECKS`.
- Produces:
  - **Spec and caps:** `SPEC_V1_SHA256`, `SPEC_V11_SHA256`, `MAX_CLAIMS`, `MAX_CAUSES`, `MAX_MISSING`, `MAX_MISSING_EVIDENCE`, `MAX_SUPPORT`, `MAX_ITEM_CHARS`, `MAX_TOTAL_CHARS`, `MAX_EXCERPTS`, `MAX_EXCERPT_CHARS`, `SUPPLEMENT_MAX_EXCERPTS`, `SUPPLEMENT_MAX_WORDS`.
  - **Key and code sets:** `PACKET_KEYS`, `KERNEL_KEYS`, `EXCERPT_KEYS`, `LABELS`, `ABSTAIN_REASONS`, `UNCERTAINTY_FINDINGS`, `ELIGIBLE_ABSTAIN_REASONS`, `PACKET_PROFILES` (a dict mapping profile to a frozenset of schema versions).
  - **Functions:**
    - `git_blob_id(data: bytes) -> str`
    - `kernel_of(result: dict) -> dict` (keys `status`, `reason`, `findings`, `checks`, `evidence`, as lists of strings)
    - `candidate_view(packet: dict) -> dict` (keys `task_id`, `observation`, `kernel`, `excerpts`, `catalog`; `catalog` is `{"findings": {id: sentence}, "checks": {id: sentence}}`)
    - `resolve_ref(ref, packet) -> bool`
    - `free_text_items(output: dict) -> list`
    - `abstention_fits(output: dict, kernel: dict) -> bool`
  - **Test helpers** (`tests/explanation_packets.py`): `T0`, `kernel_for(observation, when=T0) -> dict`, `packet(name="trend-cooling", *, task_id="t-0001", label="explanation_required", excerpts=None, observation=None, kernel=None) -> dict`, `ess_snapshot(alarms=True, now=T0) -> dict`, `quality_abstain_observation() -> dict`.

- [ ] **Step 1: Write the test helpers and the failing contract tests**

`tests/explanation_packets.py`:

```python
"""Public toy packets for explanation-task tests. No private case content."""
import copy
from datetime import datetime, timezone

from moa import fixtures
from moa.contracts import stamp
from moa.engine import Agent
from moa.evidence import EvidenceStore
from moa.explanation.contract import kernel_of
from moa.providers import Baseline

T0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def kernel_for(observation, when=T0):
    store = EvidenceStore(":memory:")
    try:
        return kernel_of(Agent(store, Baseline(), clock=lambda: when).assess(copy.deepcopy(observation)))
    finally:
        store.close()


def ess_snapshot(alarms=True, now=T0):
    t = stamp(now)
    return {"schema_version": "1.0", "snapshot_id": "authored-snapshot", "captured_at": t, "profile": "ess-u1-v1",
            "source": {"kind": "synthetic", "adapter": "ess-v1", "revision": "authored-v1", "model_id": "authored-v1"},
            "tags": [{"id": "TIC201", "value": 150, "unit": "DEG C", "quality": "good", "observed_at": t},
                     {"id": "TIC202", "value": 40, "unit": "DEG C", "quality": "good", "observed_at": t},
                     {"id": "FIC102", "value": 60, "unit": "M3/H", "quality": "good", "observed_at": t}],
            "alarms": [{"id": "reactor-hi", "tag": "TIC201", "condition": "PVHI", "priority": "High", "state": "UNACK"}] if alarms else [],
            "alarm_coverage": "complete"}


def quality_abstain_observation():
    observation = fixtures.fixture("trend-cooling", now=T0)
    observation["tags"][1]["quality"] = "bad"
    return observation


def packet(name="trend-cooling", *, task_id="t-0001", label="explanation_required", excerpts=None, observation=None, kernel=None):
    observation = fixtures.fixture(name, now=T0) if observation is None else observation
    return {"task_id": task_id, "observation": observation, "kernel": kernel_for(observation) if kernel is None else kernel,
            "excerpts": [] if excerpts is None else excerpts, "label": label}
```

`tests/test_explanation_contract.py`:

```python
import copy
import unittest
from pathlib import Path

from explanation_packets import packet, quality_abstain_observation
from moa.explanation.contract import (ELIGIBLE_ABSTAIN_REASONS, abstention_fits, candidate_view, free_text_items,
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_contract.py' -v`
Expected: `ERROR` on import with `ModuleNotFoundError: No module named 'moa.explanation'`.

- [ ] **Step 3: Write the package and the contract**

`moa/explanation/__init__.py`:

```python
"""Explanation task v1.1 evaluator: contract, template, gates, preflight and review. No model is called."""
```

`moa/explanation/contract.py`:

```python
"""Shared contract for explanation task v1.1 (docs/explanation-task-v1.1.md).

Lead-written. Every other module imports its caps, code lists and predicates
from here and never restates them. A defect here is reported, not patched
in another module.
"""

import copy
import hashlib
import re

from ..knowledge import CHECKS, FINDINGS

SPEC_V1_SHA256 = "75ab1a26444074927d9f49a34334217ced433d38fcab44281e385599105d5581"
SPEC_V11_SHA256 = "020699afd7be8d35a424e3df34339172735c0f196bd0e437a8da34d69b163dae"

MAX_CLAIMS = 12
MAX_CAUSES = 4
MAX_MISSING = 8
MAX_MISSING_EVIDENCE = 8
MAX_SUPPORT = 4
MAX_ITEM_CHARS = 240
MAX_TOTAL_CHARS = 2400
MAX_EXCERPTS = 6
MAX_EXCERPT_CHARS = 800
SUPPLEMENT_MAX_EXCERPTS = 12
SUPPLEMENT_MAX_WORDS = 200

PACKET_KEYS = frozenset({"task_id", "observation", "kernel", "excerpts", "label"})
KERNEL_KEYS = frozenset({"status", "reason", "findings", "checks", "evidence"})
EXCERPT_KEYS = frozenset({"source_id", "locator", "text"})
LABELS = frozenset({"explanation_required", "abstention_accepted"})
ABSTAIN_REASONS = frozenset({"insufficient_observation", "excerpt_conflict", "kernel_withheld", "missing_distinguishing_evidence"})
UNCERTAINTY_FINDINGS = frozenset({"cause_unresolved", "cooling_path_unconfirmed", "history_quality_gap"})
ELIGIBLE_ABSTAIN_REASONS = frozenset({
    "incomplete", "conflict", "quality", "incoherent", "units", "invalid_number",
    "history_clock", "history_sequence", "history_timing", "history_incomplete", "history_quality", "history_mismatch"})
PACKET_PROFILES = {"ess-u1-window-v1": frozenset({"1.1"}), "ess-u1-v1": frozenset({"1.0", "1.3"})}
ADVISORY_ONLY_REFS = frozenset({"policy:lab-v2", "snapshot:alarms"})
INDEX = re.compile(r"0|[1-9][0-9]*")
BAD_ESCAPE = re.compile(r"~(?![01])")


def git_blob_id(data):
    """Git's blob id for bytes, so pins are checked without running git."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def kernel_of(result):
    """The five packet kernel fields from a baseline result, as ordered lists."""
    return {"status": result["status"], "reason": result["reason"],
            "findings": [item["id"] for item in result["findings"]],
            "checks": [item["id"] for item in result["checks"]],
            "evidence": [item["ref"] for item in result["evidence"]]}


def candidate_view(packet):
    """Whitelisted candidate input (section 7): never the label, always a fresh copy."""
    view = {key: copy.deepcopy(packet[key]) for key in ("task_id", "observation", "kernel", "excerpts")}
    view["catalog"] = {"findings": {key: FINDINGS[key] for key in packet["kernel"]["findings"]},
                       "checks": {key: CHECKS[key] for key in packet["kernel"]["checks"]}}
    return view


def _pointer_resolves(document, pointer):
    if not pointer.startswith("/"):
        return False
    node = document
    for raw in pointer[1:].split("/"):
        if BAD_ESCAPE.search(raw):
            return False
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            if token not in node:
                return False
            node = node[token]
        elif isinstance(node, list):
            if not INDEX.fullmatch(token) or int(token) >= len(node):
                return False
            node = node[int(token)]
        else:
            return False
    return node is None or isinstance(node, (str, int, float, bool))


def resolve_ref(ref, packet):
    """True when a support ref resolves in the packet under section 3."""
    if not isinstance(ref, str) or ":" not in ref:
        return False
    kind, rest = ref.split(":", 1)
    kernel = packet["kernel"]
    if kind == "kernel":
        if rest in ("status", "reason") or rest in kernel["findings"] or rest in kernel["checks"]:
            return True
        return rest in kernel["evidence"] and (rest not in ADVISORY_ONLY_REFS or kernel["status"] == "advisory")
    if kind == "excerpt":
        return bool(INDEX.fullmatch(rest)) and int(rest) < len(packet["excerpts"])
    if kind == "observation":
        return _pointer_resolves(packet["observation"], rest)
    return False


def free_text_items(output):
    """Every free-text string of a shape-valid output, in document order (section 4)."""
    items = [claim["statement"] for claim in output.get("claims", [])]
    for cause in output.get("causes", []):
        items.append(cause["statement"])
        items.extend(cause["missing"])
    items.extend(output.get("missing_evidence", []))
    return items


def abstention_fits(output, kernel):
    """Section 5: kernel_withheld only on an abstaining kernel, the other three only on an advisory one."""
    if output.get("kind") != "abstain" or output.get("reason") not in ABSTAIN_REASONS:
        return False
    return (output["reason"] == "kernel_withheld") == (kernel["status"] == "abstain")
```

- [ ] **Step 4: Run the contract tests and the freeze**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_*.py' -v`
Expected: `OK`. The contract tests plus the 3 freeze tests all pass.

- [ ] **Step 5: Commit**

```bash
git add moa/explanation/__init__.py moa/explanation/contract.py tests/explanation_packets.py tests/test_explanation_contract.py
git commit -m "feat(explanation): shared v1.1 contract: caps, codes, candidate view and reference grammar"
```

---

### Task 3: Template and always-abstain control

**Files:**
- Create: `moa/explanation/template.py`
- Test: `tests/test_explanation_template.py`

**Interfaces:**
- Consumes: `candidate_view` (the view's `kernel` and `catalog`), from Task 2.
- Produces: `template(view: dict) -> dict` and `always_abstain(view: dict) -> dict`, both returning section 4 output objects.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_template.py' -v`
Expected: `ERROR` with `ModuleNotFoundError: No module named 'moa.explanation.template'`.

- [ ] **Step 3: Implement**

```python
"""Section 6 template and the section 7 always-abstain control.

The template reads the view's kernel and catalog only. It ignores excerpts
and writes no text of its own except the one fixed abstention sentence.
"""

COOLING_CAUSE_MISSING = ("compare_independent_measurement", "review_cooling_evidence")


def template(view):
    kernel = view["kernel"]
    if kernel["status"] == "abstain":
        return {"kind": "abstain", "reason": "kernel_withheld",
                "missing_evidence": [f"An observation that passes the validator check named by kernel reason {kernel['reason']}."]}
    findings, checks = view["catalog"]["findings"], view["catalog"]["checks"]
    claims = [{"statement": findings[key], "support": ["kernel:" + key]} for key in kernel["findings"]]
    causes = [{"statement": findings[key], "status": "unconfirmed", "support": ["kernel:" + key],
               "missing": list(COOLING_CAUSE_MISSING)} for key in kernel["findings"] if key == "cooling_path_unconfirmed"]
    return {"kind": "explain", "claims": claims, "causes": causes,
            "missing_evidence": [checks[key] for key in kernel["checks"]]}


def always_abstain(view):
    return {"kind": "abstain", "reason": "insufficient_observation", "missing_evidence": ["Not assessed."]}
```

- [ ] **Step 4: Run the explanation tests**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_*.py' -v`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add moa/explanation/template.py tests/test_explanation_template.py
git commit -m "feat(explanation): section 6 template and always-abstain control"
```

---

### Task 4: Enumerator of reachable window kernels and the measured caps

**Files:**
- Create: `moa/explanation/enumerate.py`
- Test: `tests/test_explanation_enumerate.py`

**Interfaces:**
- Consumes: `template`, `candidate_view` and `free_text_items` (Tasks 2 and 3).
- Produces:
  - `T0`;
  - `window_observation(series: dict, *, alarms=True, unreliable=False, now=T0) -> dict`;
  - `reachable_window_outcomes() -> dict`, mapping `(tuple finding ids, tuple check ids)` to `{"series", "alarms", "unreliable"}`.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_enumerate.py' -v`
Expected: `ERROR` with `ModuleNotFoundError: No module named 'moa.explanation.enumerate'`.

- [ ] **Step 3: Implement**

```python
"""Public enumerator of reachable window kernels, so caps are measured, not inferred.

The grid covers every finding the window rules can emit: a 4-sample reactor
series over six levels, jacket, feed and level deltas on both sides of their
thresholds, coolant output on both sides of 95 percent, alarms on or off, and
one unreliable history sample on or off. It reaches 202 distinct outcomes.
"""

import itertools
from datetime import datetime, timezone

from ..contracts import stamp
from ..knowledge import eligible

T0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
UNITS = {"TIC201": "DEG C", "TIC202": "DEG C", "FIC102": "M3/H", "LIC101": "%", "TIC202.OP": "%"}


def window_observation(series, *, alarms=True, unreliable=False, now=T0):
    t = stamp(now)
    samples = []
    for index in range(len(series["TIC201"])):
        quality = {tag: "good" for tag in UNITS}
        if unreliable and index == 1:
            quality["TIC201"] = "bad"
        samples.append({"sequence": index, "elapsed_s": index * 10,
                        "values": {tag: series[tag][index] for tag in UNITS}, "quality": quality})
    return {"schema_version": "1.1", "snapshot_id": "enumerated-window", "captured_at": t, "profile": "ess-u1-window-v1",
            "source": {"kind": "synthetic", "adapter": "ess-window-v1", "revision": "enumerated-v1", "model_id": "enumerated-v1"},
            "tags": [{"id": tag, "value": samples[-1]["values"][tag], "unit": unit, "quality": "good", "observed_at": t}
                     for tag, unit in UNITS.items()],
            "alarms": [{"id": "a1", "tag": "TIC201", "condition": "PVHI", "priority": "High", "state": "UNACK"}] if alarms else [],
            "alarm_coverage": "complete",
            "history": {"clock": "simulation_seconds", "epoch_id": "enumerated", "sequence": len(samples) - 1,
                        "sample_period_s": 10, "samples": samples}}


def reachable_window_outcomes():
    """Map each distinct (finding ids, check ids) pair to one witness."""
    seen = {}
    for reactor in itertools.product((0, 1, 2, 3, 5, 10), repeat=4):
        for jacket, feed, level, output, alarms, unreliable in itertools.product(
                (0, 3, -3), (0, 5), (0, 3), (94, 95), (True, False), (False, True)):
            series = {"TIC201": list(reactor), "TIC202": [10, 10, 10, 10 + jacket], "FIC102": [20, 20, 20, 20 + feed],
                      "LIC101": [30, 30, 30, 30 + level], "TIC202.OP": [50, 50, 50, output]}
            findings, checks, _, _ = eligible(window_observation(series, alarms=alarms, unreliable=unreliable))
            seen.setdefault((tuple(findings), tuple(checks)), {"series": series, "alarms": alarms, "unreliable": unreliable})
    return seen
```

- [ ] **Step 4: Run the explanation tests**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_*.py' -v`
Expected: `OK`. The enumerator was measured on 2026-10-03 to give 202 outcomes, 9 maximum findings, 14 maximum findings plus checks, and template maxima of 9, 1, 5, 224 and 1826.

- [ ] **Step 5: Commit**

```bash
git add moa/explanation/enumerate.py tests/test_explanation_enumerate.py
git commit -m "feat(explanation): public enumerator pinning the measured caps"
```

---

### Task 5: Mechanical checks (advisory, never a verdict)

**Files:**
- Create: `moa/explanation/mechanical.py`
- Test: `tests/test_explanation_mechanical.py`

**Interfaces:**
- Consumes: the caps, `ABSTAIN_REASONS`, `UNCERTAINTY_FINDINGS`, `free_text_items` and `resolve_ref` (Task 2); `reachable_window_outcomes` (Task 4); `template` and `always_abstain` (Task 3).
- Produces:
  - `HEADING = "mechanical check (not a reviewer verdict)"`;
  - `output_problems(output, packet) -> list[str]`: sorted problem codes from `abstain_reason`, `causes_count`, `claims_count`, `fields`, `foreign_sentence`, `item_chars`, `kind`, `missing_count`, `missing_evidence_count`, `missing_evidence_empty`, `new_id`, `not_object`, `ref_unresolved`, `status_value`, `support_count`, `support_repeat`, `support_universal_only`, `total_chars` and `type`.

- [ ] **Step 1: Write the failing tests**

```python
import copy
import unittest

from explanation_packets import packet, quality_abstain_observation
from moa.explanation.contract import ELIGIBLE_ABSTAIN_REASONS, candidate_view
from moa.explanation.enumerate import reachable_window_outcomes
from moa.explanation.mechanical import HEADING, output_problems
from moa.explanation.template import always_abstain, template
from moa.knowledge import CHECKS, FINDINGS


def kernel_packet(status, reason, findings=(), checks=(), evidence=()):
    return {"task_id": "x", "observation": {}, "excerpts": [], "label": "explanation_required",
            "kernel": {"status": status, "reason": reason, "findings": list(findings), "checks": list(checks), "evidence": list(evidence)}}


def claim(text, *refs):
    return {"statement": text, "support": list(refs) or ["kernel:reported_alarms"]}


def explain(claims, causes=(), needs=("A clean window.",)):
    return {"kind": "explain", "claims": list(claims), "causes": list(causes), "missing_evidence": list(needs)}


class MechanicalTests(unittest.TestCase):
    def setUp(self):
        self.case = packet("trend-cooling")

    def test_heading_text(self):
        self.assertEqual(HEADING, "mechanical check (not a reviewer verdict)")

    def test_template_and_control_pass_on_every_reachable_window(self):
        for findings, checks in reachable_window_outcomes():
            case = kernel_packet("advisory", "supported", findings, checks, ["snapshot:alarms", "policy:lab-v2"])
            self.assertEqual(output_problems(template(candidate_view(case)), case), [], (findings, checks))
            self.assertEqual(output_problems(always_abstain(candidate_view(case)), case), [])

    def test_template_passes_on_every_eligible_withheld_kernel(self):
        for reason in sorted(ELIGIBLE_ABSTAIN_REASONS):
            case = kernel_packet("abstain", reason)
            self.assertEqual(output_problems(template(candidate_view(case)), case), [], reason)

    def test_shape_problems(self):
        good = explain([claim("Alarms are reported.")])
        cases = [
            ([], ["not_object"]),
            ({"kind": "summary"}, ["kind"]),
            (dict(good, extra=1), ["fields"]),
            (explain([]), ["claims_count"]),
            (explain([claim("x")] * 13), ["claims_count"]),
            (explain([claim("x")], causes=[{"statement": "c", "status": "unconfirmed", "support": ["kernel:status"], "missing": ["m"]}] * 5), ["causes_count"]),
            (explain([claim("x")], needs=["n"] * 9), ["missing_evidence_count"]),
            (explain([{"statement": "x"}]), ["fields"]),
            (explain([claim("x")], causes=[{"statement": "c", "status": "confirmed", "support": ["kernel:status"], "missing": ["m"]}]), ["status_value"]),
            (explain([claim("x")], causes=[{"statement": "c", "status": "unconfirmed", "support": ["kernel:status"], "missing": []}]), ["missing_count"]),
            (explain([{"statement": 5, "support": ["kernel:status"]}]), ["type"]),
            ({"kind": "abstain", "reason": "bored", "missing_evidence": ["x"]}, ["abstain_reason"]),
            ({"kind": "abstain", "reason": "kernel_withheld", "missing_evidence": []}, ["missing_evidence_count"]),
        ]
        for output, expected in cases:
            with self.subTest(output=str(output)[:80]):
                self.assertEqual(output_problems(output, self.case), expected)

    def test_support_problems(self):
        cases = [
            ([claim("x", "kernel:status", "kernel:reason", "kernel:reported_alarms", "kernel:reactor_warming", "kernel:jacket_warming")], ["support_count"]),
            ([{"statement": "x", "support": []}], ["support_count"]),
            ([claim("x", "kernel:status", "kernel:status")], ["support_repeat"]),
            ([claim("x", "kernel:reactor_cooling")], ["ref_unresolved"]),
            ([claim("x", "kernel:policy:lab-v2")], ["support_universal_only"]),
            ([claim("x", "kernel:policy:lab-v2", "kernel:snapshot:alarms")], ["support_universal_only"]),
            ([claim("x", "kernel:policy:lab-v2", "observation:/captured_at")], []),
        ]
        for claims, expected in cases:
            with self.subTest(claims=claims):
                self.assertEqual(output_problems(explain(claims), self.case), expected)

    def test_missing_evidence_may_be_empty_only_without_open_uncertainty(self):
        self.assertEqual(output_problems(explain([claim("x")], needs=[]), self.case), ["missing_evidence_empty"])
        quiet = kernel_packet("advisory", "supported", ["no_reported_alarms"], ["continue_observation"], ["snapshot:alarms", "policy:lab-v2"])
        self.assertEqual(output_problems(explain([claim("x", "kernel:no_reported_alarms")], needs=[]), quiet), [])
        withheld = packet(observation=quality_abstain_observation())
        self.assertEqual(output_problems(explain([claim("Withheld.", "kernel:status")], needs=[]), withheld), ["missing_evidence_empty"])

    def test_ids_and_sentences_outside_the_kernel(self):
        self.assertEqual(output_problems(explain([claim("See reactor_cooling here.")]), self.case), ["new_id"])
        self.assertEqual(output_problems(explain([claim(FINDINGS["reactor_cooling"])]), self.case), ["foreign_sentence"])
        self.assertEqual(output_problems(explain([claim("x")], needs=[CHECKS["review_feed_balance"]]), self.case), ["foreign_sentence"])
        self.assertEqual(output_problems(explain([claim(FINDINGS["reactor_warming"], "kernel:reactor_warming")]), self.case), [])

    def test_caps_count_code_points(self):
        self.assertEqual(output_problems(explain([claim("\U0001F600" * 240)]), self.case), [])
        self.assertEqual(output_problems(explain([claim("\U0001F600" * 241)]), self.case), ["item_chars"])
        self.assertEqual(output_problems(explain([claim("é" * 210)] * 12), self.case), ["total_chars"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_mechanical.py' -v`
Expected: `ERROR` with `ModuleNotFoundError: No module named 'moa.explanation.mechanical'`.

- [ ] **Step 3: Implement**

```python
"""Mechanical part of criteria 1 and 6 (section 8). Advisory input beside the review sheet, never a verdict."""

import re

from ..knowledge import CHECKS, FINDINGS
from .contract import (ABSTAIN_REASONS, MAX_CAUSES, MAX_CLAIMS, MAX_ITEM_CHARS, MAX_MISSING, MAX_MISSING_EVIDENCE,
                       MAX_SUPPORT, MAX_TOTAL_CHARS, UNCERTAINTY_FINDINGS, free_text_items, resolve_ref)

HEADING = "mechanical check (not a reviewer verdict)"
CATALOG = {**FINDINGS, **CHECKS}
UNIVERSAL = frozenset({"kernel:policy:lab-v2", "kernel:snapshot:alarms"})
STRUCTURAL = frozenset({"kind", "fields", "claims_count", "causes_count", "missing_evidence_count", "missing_count"})


def _support_problems(support, packet):
    if not isinstance(support, list) or not 1 <= len(support) <= MAX_SUPPORT or not all(isinstance(ref, str) for ref in support):
        return {"support_count"}
    found = set()
    if len(set(support)) != len(support):
        found.add("support_repeat")
    if not all(resolve_ref(ref, packet) for ref in support):
        found.add("ref_unresolved")
    if set(support) <= UNIVERSAL:
        found.add("support_universal_only")
    return found


def _abstain_problems(output):
    if set(output) != {"kind", "reason", "missing_evidence"}:
        return {"fields"}
    found = set() if output["reason"] in ABSTAIN_REASONS else {"abstain_reason"}
    needs = output["missing_evidence"]
    if not isinstance(needs, list) or not 1 <= len(needs) <= MAX_MISSING_EVIDENCE:
        found.add("missing_evidence_count")
    return found


def _explain_problems(output, packet):
    if set(output) != {"kind", "claims", "causes", "missing_evidence"}:
        return {"fields"}
    claims, causes, needs = output["claims"], output["causes"], output["missing_evidence"]
    found = set()
    if not isinstance(claims, list) or not 1 <= len(claims) <= MAX_CLAIMS:
        found.add("claims_count")
    if not isinstance(causes, list) or len(causes) > MAX_CAUSES:
        found.add("causes_count")
    if not isinstance(needs, list) or len(needs) > MAX_MISSING_EVIDENCE:
        found.add("missing_evidence_count")
    if found:
        return found
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {"statement", "support"}:
            return found | {"fields"}
        found |= _support_problems(claim["support"], packet)
    for cause in causes:
        if not isinstance(cause, dict) or set(cause) != {"statement", "status", "support", "missing"}:
            return found | {"fields"}
        if cause["status"] != "unconfirmed":
            found.add("status_value")
        if not isinstance(cause["missing"], list) or not 1 <= len(cause["missing"]) <= MAX_MISSING:
            return found | {"missing_count"}
        found |= _support_problems(cause["support"], packet)
    kernel = packet["kernel"]
    may_be_empty = kernel["status"] == "advisory" and not UNCERTAINTY_FINDINGS & set(kernel["findings"]) and not causes
    if not needs and not may_be_empty:
        found.add("missing_evidence_empty")
    return found


def _id_problems(texts, kernel):
    allowed = set(kernel["findings"]) | set(kernel["checks"])
    found = set()
    for key, sentence in CATALOG.items():
        if key in allowed:
            continue
        pattern = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(key) + r"(?![A-Za-z0-9_])")
        for text in texts:
            if pattern.search(text):
                found.add("new_id")
            if sentence in text:
                found.add("foreign_sentence")
    return found


def output_problems(output, packet):
    """Sorted mechanical problem codes for one candidate output. An empty list means none were found."""
    if not isinstance(output, dict):
        return ["not_object"]
    kind = output.get("kind")
    if kind == "abstain":
        found = _abstain_problems(output)
    elif kind == "explain":
        found = _explain_problems(output, packet)
    else:
        return ["kind"]
    if found & STRUCTURAL:
        return sorted(found)
    texts = free_text_items(output)
    if not all(isinstance(text, str) for text in texts):
        return sorted(found | {"type"})
    if any(len(text) > MAX_ITEM_CHARS for text in texts):
        found.add("item_chars")
    if sum(len(text) for text in texts) > MAX_TOTAL_CHARS:
        found.add("total_chars")
    return sorted(found | _id_problems(texts, packet["kernel"]))
```

- [ ] **Step 4: Run the explanation tests**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_*.py' -v`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add moa/explanation/mechanical.py tests/test_explanation_mechanical.py
git commit -m "feat(explanation): advisory mechanical checks for criteria 1 and 6"
```

---

### Task 6: Packet gates: parse, eligibility, leak words, supplement

**Files:**
- Create: `moa/data/explanation-leak-words.json`
- Create: `moa/explanation/eligibility.py`
- Test: `tests/test_explanation_eligibility.py`

**Interfaces:**
- Consumes: Task 2 constants.
- Produces:
  - `LEAK_WORDS_PATH`;
  - `load_leak_words(path=LEAK_WORDS_PATH) -> tuple`;
  - `parse_gate(packet) -> str | None`, giving `"parse"` or `"kernel_sentences"`;
  - `timestamps_ok(observation) -> bool`;
  - `leaks(packet, words) -> bool`;
  - `eligibility_problem(packet, words) -> str | None`, giving `"profile"`, `"reason"`, `"timestamp"`, `"leak"` or `"duplicate_excerpt"`;
  - `supplement_problems(packets) -> list`, giving `"supplement_count"` and/or `"supplement_words"`.

- [ ] **Step 1: Write the word list file and the failing tests**

`moa/data/explanation-leak-words.json`:

```json
{
  "schema": "moa-explanation-leak-words-v1",
  "sources": {
    "moa/data/drills-v1.json": "56edad87ad67484af62e5401f14cdf171112ef47",
    "moa/data/drills-v2.json": "3fd23f4a068202d82699049450b35de4a6a40a84",
    "moa/fixtures.py": "94fc836c657b470b8976c321134e84012bbae415"
  },
  "label_words": ["abstention_accepted", "explanation_required"],
  "words": ["abstention_accepted", "bad-quality", "conflict", "cooling", "cooling-loss", "explanation_required", "feed-surge", "history-gap", "history-quality", "injection", "missing", "normal", "partial", "recovery", "restoration-lag", "stale", "trend-cooling", "trend-recovery"]
}
```

`tests/test_explanation_eligibility.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_eligibility.py' -v`
Expected: `ERROR` with `ModuleNotFoundError: No module named 'moa.explanation.eligibility'`.

- [ ] **Step 3: Implement**

```python
"""Section 1 and section 2 packet gates: parse, profile, reason, timestamps, leak words, excerpts, supplement."""

import json
import math
import re
from pathlib import Path

from ..contracts import Rejected, canonical, strict_json
from .contract import (ELIGIBLE_ABSTAIN_REASONS, EXCERPT_KEYS, KERNEL_KEYS, LABELS, MAX_EXCERPT_CHARS, MAX_EXCERPTS,
                       PACKET_KEYS, PACKET_PROFILES, SUPPLEMENT_MAX_EXCERPTS, SUPPLEMENT_MAX_WORDS)

LEAK_WORDS_PATH = Path(__file__).resolve().parents[1] / "data" / "explanation-leak-words.json"
TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T([0-9]{2}):[0-9]{2}:[0-9]{2}(\.[0-9]{3}|\.[0-9]{6})?Z")


def load_leak_words(path=LEAK_WORDS_PATH):
    return tuple(json.loads(Path(path).read_text())["words"])


def _finite(value):
    if value is None or isinstance(value, (bool, str)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, int):
        try:
            float(value)
        except OverflowError:
            return False
        return True
    if isinstance(value, list):
        return all(_finite(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _finite(item) for key, item in value.items())
    return False


def parse_gate(packet):
    """None when the packet has exactly the v1 fields and a finite JSON observation, else a category."""
    if not isinstance(packet, dict) or set(packet) != PACKET_KEYS:
        return "parse"
    if not isinstance(packet["task_id"], str) or packet["label"] not in LABELS:
        return "parse"
    kernel, excerpts, observation = packet["kernel"], packet["excerpts"], packet["observation"]
    if (not isinstance(kernel, dict) or set(kernel) != KERNEL_KEYS or not isinstance(kernel["status"], str)
            or not isinstance(kernel["reason"], str) or not all(isinstance(kernel[key], list) for key in ("findings", "checks", "evidence"))):
        return "parse"
    if any(isinstance(item, dict) for key in ("findings", "checks") for item in kernel[key]):
        return "kernel_sentences"
    if not all(isinstance(item, str) for key in ("findings", "checks", "evidence") for item in kernel[key]):
        return "parse"
    if not isinstance(excerpts, list) or len(excerpts) > MAX_EXCERPTS:
        return "parse"
    for excerpt in excerpts:
        if (not isinstance(excerpt, dict) or set(excerpt) != EXCERPT_KEYS
                or not all(isinstance(excerpt[key], str) for key in EXCERPT_KEYS) or len(excerpt["text"]) > MAX_EXCERPT_CHARS):
            return "parse"
    if not isinstance(observation, dict) or not _finite(observation):
        return "parse"
    try:
        strict_json(canonical(observation))
    except (Rejected, ValueError, TypeError, OverflowError, RecursionError):
        return "parse"
    return None


def timestamps_ok(observation):
    tags = observation.get("tags") if isinstance(observation.get("tags"), list) else []
    values = [observation.get("captured_at")] + [tag.get("observed_at") for tag in tags if isinstance(tag, dict)]
    for value in values:
        match = TIMESTAMP.fullmatch(value) if isinstance(value, str) else None
        if match is None or int(match.group(1)) > 23:
            return False
    return True


def _tokens(value):
    return [token for token in re.split(r"[^a-z0-9]+", value.lower()) if token]


def _identifier_leaks(value, words):
    tokens = _tokens(value)
    for word in words:
        target = _tokens(word)
        if any(tokens[i:i + len(target)] == target for i in range(len(tokens) - len(target) + 1)):
            return True
    return False


def _text_leaks(value, words):
    lowered = value.lower()
    return any(word in lowered for word in words if "-" in word or "_" in word)


def _leak_fields(packet):
    observation = packet["observation"]
    source = observation.get("source") if isinstance(observation.get("source"), dict) else {}
    history = observation.get("history") if isinstance(observation.get("history"), dict) else {}
    identifiers = [packet["task_id"], observation.get("snapshot_id"), history.get("epoch_id"), source.get("model_id"), source.get("revision")]
    texts = []
    for alarm in observation.get("alarms") if isinstance(observation.get("alarms"), list) else []:
        if isinstance(alarm, dict):
            identifiers.append(alarm.get("id"))
            texts.extend(alarm.get(key) for key in ("condition", "priority", "state"))
    for excerpt in packet["excerpts"]:
        identifiers.extend((excerpt["source_id"], excerpt["locator"]))
        texts.append(excerpt["text"])
    return [v for v in identifiers if isinstance(v, str)], [v for v in texts if isinstance(v, str)]


def leaks(packet, words):
    identifiers, texts = _leak_fields(packet)
    return any(_identifier_leaks(value, words) for value in identifiers) or any(_text_leaks(value, words) for value in texts)


def eligibility_problem(packet, words):
    """None when a parsed packet is eligible under section 1, else a category."""
    observation, kernel = packet["observation"], packet["kernel"]
    profile = observation.get("profile")
    versions = PACKET_PROFILES.get(profile) if isinstance(profile, str) else None
    if versions is None or observation.get("schema_version") not in versions:
        return "profile"
    if kernel["status"] != "advisory" and (kernel["status"] != "abstain" or kernel["reason"] not in ELIGIBLE_ABSTAIN_REASONS):
        return "reason"
    if not timestamps_ok(observation):
        return "timestamp"
    if leaks(packet, words):
        return "leak"
    pairs = [(excerpt["source_id"], excerpt["locator"]) for excerpt in packet["excerpts"]]
    if len(set(pairs)) != len(pairs):
        return "duplicate_excerpt"
    return None


def supplement_problems(packets):
    """Package-level sizing ruling: at most 12 distinct excerpts, each at most 200 words."""
    distinct = {(excerpt["source_id"], excerpt["locator"], excerpt["text"]) for packet in packets for excerpt in packet["excerpts"]}
    problems = []
    if len(distinct) > SUPPLEMENT_MAX_EXCERPTS:
        problems.append("supplement_count")
    if any(len(text.split()) > SUPPLEMENT_MAX_WORDS for _, _, text in distinct):
        problems.append("supplement_words")
    return problems
```

- [ ] **Step 4: Run the explanation tests**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_*.py' -v`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add moa/data/explanation-leak-words.json moa/explanation/eligibility.py tests/test_explanation_eligibility.py
git commit -m "feat(explanation): section 1 packet gates and pinned leak word list"
```

---

### Task 7: Preflight

**Files:**
- Create: `moa/explanation/preflight.py`
- Test: `tests/test_explanation_preflight.py`

**Interfaces:**
- Consumes: `kernel_of`, `git_blob_id` and `SPEC_V11_SHA256` (Task 2); `parse_gate`, `eligibility_problem`, `load_leak_words` and `supplement_problems` (Task 6).
- Produces:
  - `ROOT`;
  - `MANIFEST_KEYS = ("catalog_commit", "manifest_sha256", "review_sha256", "grid_sha256", "validation_clocks", "author_python")`;
  - `Refused(code)`, with `.code` in `{"manifest", "review", "catalog"}`;
  - `freeze_check(manifest, root=ROOT) -> str`, returning the catalog blob;
  - `rerun_kernel(observation, when) -> dict`;
  - `preflight(packets, manifest, *, words=None, root=ROOT) -> {"public": dict, "private": {"valid_task_ids": list}}`. The public keys are `schema`, `spec_sha256`, `packets`, `valid_count`, `valid_set_sha256`, `invalid_counts`, `package_problems`, `manifest_sha256`, `clock_manifest_sha256`, `leak_words_sha256`, `catalog_blob`, `python`, `author_python` and `runnable`.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_preflight.py' -v`
Expected: `ERROR` with `ModuleNotFoundError: No module named 'moa.explanation.preflight'`.

- [ ] **Step 3: Implement**

```python
"""Section 2 preflight. Runs over every packet before any candidate and reports counts and hashes only. Never prints."""

import copy
import platform
import re
import subprocess
from pathlib import Path

from ..contracts import Rejected, digest, timestamp
from ..engine import Agent
from ..evidence import EvidenceStore
from ..providers import Baseline
from .contract import SPEC_V11_SHA256, git_blob_id, kernel_of
from .eligibility import eligibility_problem, load_leak_words, parse_gate, supplement_problems

ROOT = Path(__file__).resolve().parents[2]
COMMIT = re.compile(r"[0-9a-f]{7,40}")
MANIFEST_KEYS = ("catalog_commit", "manifest_sha256", "review_sha256", "grid_sha256", "validation_clocks", "author_python")
MESSAGES = {"manifest": "The case manifest is missing a required field.",
            "review": "The case freeze has no recorded independent review.",
            "catalog": "The catalog at the case freeze commit does not match this checkout."}


class Refused(RuntimeError):
    def __init__(self, code):
        super().__init__(MESSAGES[code])
        self.code = code


def catalog_blob_at(commit, root=ROOT):
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        return None
    process = subprocess.run(["git", "-C", str(root), "rev-parse", f"{commit}:moa/knowledge.py"], capture_output=True, text=True)
    return process.stdout.strip() if process.returncode == 0 else None


def freeze_check(manifest, root=ROOT):
    """Section 2 step 1. Returns the catalog blob, or raises Refused with a fixed message."""
    if not isinstance(manifest, dict) or any(key not in manifest for key in MANIFEST_KEYS) or not isinstance(manifest["validation_clocks"], dict):
        raise Refused("manifest")
    if not manifest["review_sha256"]:
        raise Refused("review")
    working = git_blob_id((Path(root) / "moa" / "knowledge.py").read_bytes())
    if catalog_blob_at(manifest["catalog_commit"], root) != working:
        raise Refused("catalog")
    return working


def rerun_kernel(observation, when):
    store = EvidenceStore(":memory:")
    try:
        return kernel_of(Agent(store, Baseline(), clock=lambda: when).assess(copy.deepcopy(observation)))
    finally:
        store.close()


def preflight(packets, manifest, *, words=None, root=ROOT):
    """Gate every packet and rerun its kernel at the section 1 clock. Public part holds counts and hashes only."""
    catalog = freeze_check(manifest, root)
    words = load_leak_words() if words is None else tuple(words)
    counts, valid, seen, parsed = {}, [], set(), []
    for packet in packets:
        category = parse_gate(packet)
        if category is None:
            parsed.append(packet)
            if packet["task_id"] in seen:
                category = "duplicate_task_id"
            seen.add(packet["task_id"])
        category = category or eligibility_problem(packet, words)
        when = None
        if category is None:
            try:
                when = timestamp(manifest["validation_clocks"].get(packet["task_id"]) or packet["observation"]["captured_at"])
            except Rejected:
                category = "clock"
        if category is None and rerun_kernel(packet["observation"], when) != packet["kernel"]:
            category = "kernel_mismatch"
        if category:
            counts[category] = counts.get(category, 0) + 1
        else:
            valid.append(packet["task_id"])
    package = supplement_problems(parsed)
    valid = sorted(valid)
    public = {"schema": "moa-explanation-preflight-v1", "spec_sha256": SPEC_V11_SHA256, "packets": len(packets),
              "valid_count": len(valid), "valid_set_sha256": digest(valid), "invalid_counts": dict(sorted(counts.items())),
              "package_problems": package, "manifest_sha256": manifest["manifest_sha256"],
              "clock_manifest_sha256": digest(manifest["validation_clocks"]), "leak_words_sha256": digest(sorted(words)),
              "catalog_blob": catalog, "python": platform.python_version(), "author_python": manifest["author_python"],
              "runnable": bool(packets) and not counts and not package and len(valid) == len(packets)}
    return {"public": public, "private": {"valid_task_ids": valid}}
```

- [ ] **Step 4: Run the explanation tests**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_*.py' -v`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add moa/explanation/preflight.py tests/test_explanation_preflight.py
git commit -m "feat(explanation): section 2 preflight with fixed-clock kernel rerun"
```

---

### Task 8: Evaluation run

**Files:**
- Create: `moa/explanation/evaluate.py`
- Test: `tests/test_explanation_evaluate.py`

**Interfaces:**
- Consumes:
  - `candidate_view`, `abstention_fits`, `git_blob_id`, `SPEC_V1_SHA256` and `SPEC_V11_SHA256` (Task 2);
  - `template` and `always_abstain` (Task 3);
  - `HEADING` and `output_problems` (Task 5);
  - `ROOT` and `preflight` (Task 7).
- Produces:
  - `RUN_MODES`, `Aborted(code)` (codes `preflight`, `grid`, `valid_set`, `model_freeze`) and `case_hash(packet) -> str`;
  - `call_once(candidate, view) -> (output | None, failure | None)`, with failure in `{"exception", "non_json", "non_object"}`;
  - `evaluate(packets, manifest, recorded_preflight, *, model=None, model_freeze=None, root=ROOT) -> {"public": run_record, "private": {"rows": [...], "packets": {case_hash: packet}}}`.
  - Each row has `case_hash`, `label`, `kernel_status`, `candidate`, `run_mode`, `output`, `failure`, `mechanical` (`{"heading", "problems"}`) and `abstention_fits`.

- [ ] **Step 1: Write the failing tests**

```python
import copy
import unittest

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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_evaluate.py' -v`
Expected: `ERROR` with `ModuleNotFoundError: No module named 'moa.explanation.evaluate'`.

- [ ] **Step 3: Implement**

```python
"""Section 7 run: each candidate once per valid packet, mechanical checks beside each output. Never prints."""

import copy
import hashlib
import platform

from ..contracts import Rejected, canonical, digest, strict_json
from .contract import SPEC_V1_SHA256, SPEC_V11_SHA256, abstention_fits, candidate_view, git_blob_id
from .mechanical import HEADING, output_problems
from .preflight import ROOT, preflight
from .template import always_abstain, template

RUN_MODES = {"template": "deterministic template", "always-abstain": "deterministic always-abstain", "model": "model"}
MODEL_FREEZE_KEYS = ("prompt_sha256", "model_id", "model_digest", "decoding_sha256", "schema_sha256")
RECORD_FILES = ("moa/knowledge.py", "moa/contracts.py", "moa/engine.py", "moa/providers.py", "moa/evidence.py",
                "moa/fixtures.py", "moa/data/drills-v1.json", "moa/data/drills-v2.json", "moa/data/explanation-leak-words.json")
MESSAGES = {"preflight": "Preflight did not pass; no candidate was run.",
            "grid": "The reviewer grid is not frozen; no candidate was run.",
            "valid_set": "The valid set differs from the recorded preflight; the run is aborted.",
            "model_freeze": "A model candidate needs its frozen prompt, model and decoding hashes."}


class Aborted(RuntimeError):
    def __init__(self, code):
        super().__init__(MESSAGES[code])
        self.code = code


def case_hash(packet):
    return digest(packet)


def call_once(candidate, view):
    """One attempt, no retry, no repair. Returns (output, failure)."""
    try:
        output = candidate(copy.deepcopy(view))
    except Exception:
        return None, "exception"
    try:
        output = strict_json(canonical(output))
    except (Rejected, ValueError, TypeError, OverflowError, RecursionError):
        return None, "non_json"
    if not isinstance(output, dict):
        return None, "non_object"
    return output, None


def _source_hash(root):
    files = sorted((root / "moa" / "explanation").glob("*.py"))
    return digest({path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files})


def _run_record(manifest, checked, root, model_freeze):
    return {"spec_frozen_against_sha256": SPEC_V1_SHA256, "spec_scored_under_sha256": SPEC_V11_SHA256,
            "manifest_sha256": manifest["manifest_sha256"], "grid_sha256": manifest["grid_sha256"],
            "valid_set_sha256": checked["valid_set_sha256"], "leak_words_sha256": checked["leak_words_sha256"],
            "blobs": {name: git_blob_id((root / name).read_bytes()) for name in RECORD_FILES},
            "python": platform.python_version(), "author_python": manifest["author_python"],
            "evaluator_source_sha256": _source_hash(root), "model_freeze": copy.deepcopy(model_freeze)}


def evaluate(packets, manifest, recorded_preflight, *, model=None, model_freeze=None, root=ROOT):
    """Run the template, the always-abstain control and, only with a frozen record, a model."""
    if not recorded_preflight["public"]["runnable"]:
        raise Aborted("preflight")
    if not manifest.get("grid_sha256"):
        raise Aborted("grid")
    candidates = {"template": template, "always-abstain": always_abstain}
    if model is not None:
        if not isinstance(model_freeze, dict) or any(not model_freeze.get(key) for key in MODEL_FREEZE_KEYS):
            raise Aborted("model_freeze")
        candidates["model"] = model
    checked = preflight(packets, manifest, root=root)["public"]
    if not checked["runnable"] or checked["valid_set_sha256"] != recorded_preflight["public"]["valid_set_sha256"]:
        raise Aborted("valid_set")
    rows = []
    for packet in sorted(packets, key=lambda item: item["task_id"]):
        view = candidate_view(packet)
        for name, candidate in candidates.items():
            output, failure = call_once(candidate, view)
            rows.append({"case_hash": case_hash(packet), "label": packet["label"], "kernel_status": packet["kernel"]["status"],
                         "candidate": name, "run_mode": RUN_MODES[name], "output": output, "failure": failure,
                         "mechanical": {"heading": HEADING, "problems": output_problems(output, packet) if output is not None else []},
                         "abstention_fits": abstention_fits(output, packet["kernel"]) if output is not None else False})
    return {"public": _run_record(manifest, checked, root, model_freeze),
            "private": {"rows": rows, "packets": {case_hash(packet): copy.deepcopy(packet) for packet in packets}}}
```

- [ ] **Step 4: Run the explanation tests**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_*.py' -v`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add moa/explanation/evaluate.py tests/test_explanation_evaluate.py
git commit -m "feat(explanation): section 7 run with failed-attempt accounting and run record"
```

---

### Task 9: Review sheet, tally of recorded verdicts, public report

**Files:**
- Create: `moa/explanation/review.py`
- Test: `tests/test_explanation_review.py`

**Interfaces:**
- Consumes: `evaluate` output from Task 8; `candidate_view`, `SPEC_V1_SHA256` and `SPEC_V11_SHA256` from Task 2; `HEADING` from Task 5.
- Produces:
  - `IncompleteReview(ValueError)`;
  - `review_sheet(run, salt) -> (sheet, key)`. The sheet has `schema`, `spec_sha256`, `single_reviewer`, `mechanical_heading`, `cases` (case_hash to view without label), `rows` and `pairs`. The key has `salt` and `rows` (row_id to `{case_hash, candidate}`) and stays private.
  - `tally(run, key, verdicts) -> {"candidates": {candidate: {kernel_status: counts}}, "preferences": {"model", "template", "tie"}}`. `verdicts` is `{"rows": {row_id: {"1".."6": "pass"|"fail", "abstention": "pass"|"fail"|None, "note": str}}, "pairs": {case_hash: row_id | "tie"}}`.
  - `public_report(run, counted) -> dict`, built from an allowlist.

- [ ] **Step 1: Write the failing tests**

```python
import json
import unittest

from explanation_packets import ess_snapshot, packet, quality_abstain_observation
from moa.explanation.evaluate import evaluate
from moa.explanation.preflight import preflight
from moa.explanation.review import IncompleteReview, public_report, review_sheet, tally
from moa.explanation.template import template

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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_review.py' -v`
Expected: `ERROR` with `ModuleNotFoundError: No module named 'moa.explanation.review'`.

- [ ] **Step 3: Implement**

```python
"""Section 8 review sheet, tally of Anthony's recorded verdicts, and the counts-only public report."""

from ..contracts import digest
from .contract import SPEC_V1_SHA256, SPEC_V11_SHA256, candidate_view
from .mechanical import HEADING

CRITERIA = ("1", "2", "3", "4", "5", "6")
VERDICTS = frozenset({"pass", "fail"})
LIMITS = ["Counts and hashes only. No benefit, safety or readiness claim.",
          "Single reviewer. Nothing here is called useful until a second human independently reviews criterion 5 without seeing these verdicts.",
          "Mechanical checks are advisory and are not reviewer verdicts."]


class IncompleteReview(ValueError):
    pass


def _row_id(salt, row):
    return digest([salt, row["case_hash"], row["candidate"]])[:16]


def review_sheet(run, salt):
    """Blank, shuffled skeleton for the reviewer, plus the private key mapping rows back to candidates."""
    on_sheet = [row for row in run["private"]["rows"] if row["candidate"] != "always-abstain" and row["output"] is not None]
    on_sheet.sort(key=lambda row: (row["case_hash"], _row_id(salt, row)))
    packets = run["private"]["packets"]
    cases = {row["case_hash"]: candidate_view(packets[row["case_hash"]]) for row in on_sheet}
    rows = [{"row_id": _row_id(salt, row), "case_hash": row["case_hash"], "output": row["output"],
             "mechanical": row["mechanical"], "abstention_reason_fits": row["abstention_fits"],
             "cells": {**{criterion: None for criterion in CRITERIA}, "abstention": None, "note": None}} for row in on_sheet]
    pairs = []
    for case in sorted(cases):
        kinds = {row["candidate"] for row in on_sheet if row["case_hash"] == case}
        if {"template", "model"} <= kinds and packets[case]["kernel"]["status"] == "advisory":
            pairs.append({"case_hash": case, "rows": [row["row_id"] for row in rows if row["case_hash"] == case],
                          "preferred": None, "note": None})
    sheet = {"schema": "moa-explanation-review-sheet-v1", "spec_sha256": SPEC_V11_SHA256, "single_reviewer": True,
             "mechanical_heading": HEADING, "cases": cases, "rows": rows, "pairs": pairs}
    key = {"salt": salt, "rows": {_row_id(salt, row): {"case_hash": row["case_hash"], "candidate": row["candidate"]} for row in on_sheet}}
    return sheet, key


def _bucket():
    return {"all_six_on_explanation_required": 0, "explanation_passes": 0, "abstention_passes": 0, "failed_attempts": 0, "outputs": 0}


def _verdict(verdicts, row_id):
    verdict = verdicts.get("rows", {}).get(row_id)
    if (not isinstance(verdict, dict) or any(verdict.get(criterion) not in VERDICTS for criterion in CRITERIA)
            or verdict.get("abstention") not in VERDICTS | {None}):
        raise IncompleteReview("Every sheet row needs a recorded pass or fail for criteria 1 to 6.")
    return verdict


def tally(run, key, verdicts):
    """Counts from the reviewer's recorded verdicts only. A row without a verdict stops the tally."""
    counts = {}
    for row in run["private"]["rows"]:
        bucket = counts.setdefault(row["candidate"], {}).setdefault(row["kernel_status"], _bucket())
        bucket["outputs"] += 1
        if row["failure"]:
            bucket["failed_attempts"] += 1
            continue
        verdict = None if row["candidate"] == "always-abstain" else _verdict(verdicts, _row_id(key["salt"], row))
        if row["output"].get("kind") == "explain":
            if verdict and all(verdict[criterion] == "pass" for criterion in CRITERIA):
                bucket["explanation_passes"] += 1
                if row["label"] == "explanation_required":
                    bucket["all_six_on_explanation_required"] += 1
        elif row["label"] == "abstention_accepted" and row["abstention_fits"] and verdict and verdict.get("abstention") == "pass":
            bucket["abstention_passes"] += 1
    preferences = {"model": 0, "template": 0, "tie": 0}
    for case, choice in verdicts.get("pairs", {}).items():
        if choice == "tie":
            preferences["tie"] += 1
        elif choice in key["rows"] and key["rows"][choice]["case_hash"] == case:
            preferences[key["rows"][choice]["candidate"]] += 1
        else:
            raise IncompleteReview("A paired judgment names a row outside its case.")
    return {"candidates": counts, "preferences": preferences}


def public_report(run, counted):
    """Counts and hashes only, labelled single-reviewer. No case hash, task id or text."""
    return {"schema": "moa-explanation-report-v1", "spec_frozen_against_sha256": SPEC_V1_SHA256,
            "spec_scored_under_sha256": SPEC_V11_SHA256, "review": "single-reviewer",
            "useful_measure": "all-six passes, single-reviewer",
            "run_modes": sorted({row["run_mode"] for row in run["private"]["rows"]}),
            "record": run["public"], "counts": counted["candidates"], "preferences": counted["preferences"], "limits": list(LIMITS)}
```

- [ ] **Step 4: Run the explanation tests**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_*.py' -v`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add moa/explanation/review.py tests/test_explanation_review.py
git commit -m "feat(explanation): blind review sheet, verdict tally and counts-only report"
```

---

### Task 10: Privacy canary, docs, full verification

**Files:**
- Create: `tests/test_explanation_privacy.py`
- Modify: `CHANGELOG.md` (the `## Unreleased` section; create it above `## 0.8.0` if absent)
- Modify: `README.md` (the `**Explanation task:**` paragraph)

**Interfaces:**
- Consumes: everything above.
- Produces: the end-to-end privacy guarantee and the user-facing notes.

- [ ] **Step 1: Write the canary test**

```python
"""Canary: private identifiers and text never reach stdout, stderr or a public object, even on failure."""
import contextlib
import io
import json
import unittest

from explanation_packets import packet
from moa.explanation.evaluate import evaluate
from moa.explanation.preflight import Refused, preflight
from moa.explanation.review import public_report, review_sheet, tally

SENTINEL = "SNTLq7x9"
FREEZE = {"prompt_sha256": "p" * 64, "model_id": "toy", "model_digest": "d" * 64, "decoding_sha256": "s" * 64, "schema_sha256": "o" * 64}
MANIFEST = {"catalog_commit": "68cb08c", "manifest_sha256": "m" * 64, "review_sha256": "r" * 64, "grid_sha256": "g" * 64,
            "validation_clocks": {}, "author_python": "3.10.12"}


class PrivacyCanaryTests(unittest.TestCase):
    def test_sentinel_never_escapes(self):
        excerpt = {"source_id": f"https://example.org/{SENTINEL}", "locator": f"p-{SENTINEL}", "text": f"{SENTINEL} private excerpt text."}
        packets = [packet(task_id=f"t-{SENTINEL}", excerpts=[excerpt])]

        def model(view):
            raise RuntimeError(f"{SENTINEL} boom")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            checked = preflight(packets, MANIFEST)
            run = evaluate(packets, MANIFEST, checked, model=model, model_freeze=FREEZE)
            sheet, key = review_sheet(run, "salt")
            verdicts = {"rows": {row["row_id"]: {**{c: "pass" for c in "123456"}, "abstention": None} for row in sheet["rows"]}, "pairs": {}}
            report = public_report(run, tally(run, key, verdicts))
            try:
                preflight(packets, dict(MANIFEST, review_sha256=None))
            except Refused as exc:
                refusal = str(exc)
        self.assertTrue(checked["public"]["runnable"])
        self.assertEqual([r["failure"] for r in run["private"]["rows"] if r["candidate"] == "model"], ["exception"])
        for public in (out.getvalue(), err.getvalue(), json.dumps(checked["public"]), json.dumps(run["public"]), json.dumps(report), refusal):
            self.assertNotIn(SENTINEL, public)
        self.assertNotIn(SENTINEL, json.dumps([r["failure"] for r in run["private"]["rows"]]))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it**

Run: `python3 -m unittest discover -s tests -p 'test_explanation_privacy.py' -v`
Expected: `OK`. This test guards behaviour already built in Tasks 7 to 9, so it passes first.

- [ ] **Step 3: Prove the canary can fail**

In `moa/explanation/evaluate.py`, temporarily change `return None, "exception"` to `return None, "exception: " + str(sys.exc_info()[1])`, adding `import sys`. Run the same command.
Expected: `FAIL` on `assertNotIn(SENTINEL, ...)`. Then revert with `git checkout moa/explanation/evaluate.py` and rerun. Expected: `OK`.

- [ ] **Step 4: Update the docs**

In `README.md`, replace the `**Explanation task:**` paragraph with:

```markdown
**Explanation task:** the [v1 contract](docs/explanation-task-v1.md) froze how a later candidate may explain findings the baseline already produced. Its [v1.1 revision](docs/explanation-task-v1.1.md), [adopted 2026-10-03](docs/explanation-task-v1.1-adoption.md), corrects v1's template and limits. `moa/explanation/` implements the v1.1 preflight, template, always-abstain control, advisory mechanical checks, blind review sheet and counts-only report. No model is called, and nothing has been run on the private cases. That needs a case-package loader, the frozen reviewer grid and an independent review of the case freeze.
```

In `CHANGELOG.md`, add under `## Unreleased`:

```markdown
- Adopt explanation-task v1.1 (Anthony, 2026-10-03, all ten decisions as recommended) and add `moa/explanation/`. It holds the shared contract, the section 6 template and always-abstain control, advisory mechanical checks, section 1 packet gates with a pinned leak word list, a fixed-clock preflight, a single-attempt evaluation run, a blind review sheet, a tally of recorded verdicts and a counts-only report. A stage 0 freeze pins the case-freeze modules, both specs and the fixture kernels. No model is called and no private case is read.
```

- [ ] **Step 5: Full verification**

Run, in order:
- `python3 -m unittest discover -s tests` → Expected: `OK (skipped=10)`.
- `node --test tests/stream-boundary.test.cjs tests/export-quality.test.cjs` → Expected: `# pass 12`, `# fail 0`, `# skipped 2`.
- `git status --short` → Expected: only the files of this task.

- [ ] **Step 6: Commit**

```bash
git add tests/test_explanation_privacy.py README.md CHANGELOG.md
git commit -m "test(explanation): privacy canary; docs for the v1.1 evaluator"
```
