"""Shared contract for explanation task v1.1 (docs/explanation-task-v1.1.md).

Lead-written. Every other module imports its caps, code lists and predicates
from here and never restates them. A defect here is reported, not patched
in another module.
"""

import copy
import hashlib
import re

from ..contracts import digest
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
INDEX = re.compile(r"0|[1-9][0-9]{0,8}")
BAD_ESCAPE = re.compile(r"~(?![01])")


def git_blob_id(data):
    """Git's blob id for bytes, so pins are checked without running git."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def case_hash(packet):
    """Hash of a packet without its label, so the hash cannot reveal the hidden label."""
    return digest({key: value for key, value in packet.items() if key != "label"})


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
    reason = output.get("reason")
    if output.get("kind") != "abstain" or not isinstance(reason, str) or reason not in ABSTAIN_REASONS:
        return False
    return (output["reason"] == "kernel_withheld") == (kernel["status"] == "abstain")
