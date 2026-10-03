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
