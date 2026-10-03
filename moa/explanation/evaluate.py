"""Section 7 run: each candidate once per valid packet, mechanical checks beside each output. Never prints."""

import copy
import hashlib
import platform

from ..contracts import Rejected, canonical, digest, strict_json
from .contract import SPEC_V1_SHA256, SPEC_V11_SHA256, abstention_fits, candidate_view, case_hash, git_blob_id
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


def _checked(output, packet):
    """Mechanical problems and abstention fit; a checker crash is a criterion 6 problem, never a lost run."""
    if output is None:
        return [], False
    try:
        return output_problems(output, packet), abstention_fits(output, packet["kernel"])
    except Exception:
        return ["malformed"], False


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
            problems, fits = _checked(output, packet)
            rows.append({"case_hash": case_hash(packet), "label": packet["label"], "kernel_status": packet["kernel"]["status"],
                         "candidate": name, "run_mode": RUN_MODES[name], "output": output, "failure": failure,
                         "mechanical": {"heading": HEADING, "problems": problems}, "abstention_fits": fits})
    return {"public": _run_record(manifest, checked, root, model_freeze),
            "private": {"rows": rows, "packets": {case_hash(packet): copy.deepcopy(packet) for packet in packets}}}
