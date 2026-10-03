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
    reason = output["reason"]
    found = set() if isinstance(reason, str) and reason in ABSTAIN_REASONS else {"abstain_reason"}
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
