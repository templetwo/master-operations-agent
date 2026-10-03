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
    key = {"salt": salt, "rows": {_row_id(salt, row): {"case_hash": row["case_hash"], "candidate": row["candidate"]} for row in on_sheet},
           "pairs": [pair["case_hash"] for pair in pairs]}
    return sheet, key


def _bucket():
    return {"all_six_on_explanation_required": 0, "explanation_passes": 0, "abstention_passes": 0, "failed_attempts": 0, "outputs": 0}


def _is_verdict(value):
    return isinstance(value, str) and value in VERDICTS


def _verdict(rows, row_id, abstained):
    verdict = rows.get(row_id)
    if not isinstance(verdict, dict) or not all(_is_verdict(verdict.get(criterion)) for criterion in CRITERIA):
        raise IncompleteReview("Every sheet row needs a recorded pass or fail for criteria 1 to 6.")
    abstention = verdict.get("abstention")
    if not (_is_verdict(abstention) if abstained else abstention is None or _is_verdict(abstention)):
        raise IncompleteReview("Every abstention row needs a recorded pass or fail for the abstention rule.")
    return verdict


def tally(run, key, verdicts):
    """Counts from the reviewer's recorded verdicts only. A row without a verdict stops the tally."""
    rows = verdicts.get("rows") if isinstance(verdicts, dict) else None
    pairs = verdicts.get("pairs") if isinstance(verdicts, dict) else None
    if not isinstance(rows, dict) or not isinstance(pairs, dict):
        raise IncompleteReview("Recorded verdicts need a rows mapping and a pairs mapping.")
    if set(pairs) != set(key["pairs"]):
        raise IncompleteReview("Every pair on the sheet needs exactly one recorded judgment.")
    counts = {}
    for row in run["private"]["rows"]:
        bucket = counts.setdefault(row["candidate"], {}).setdefault(row["kernel_status"], _bucket())
        bucket["outputs"] += 1
        if row["failure"]:
            bucket["failed_attempts"] += 1
            continue
        abstained = row["output"].get("kind") == "abstain"
        verdict = None if row["candidate"] == "always-abstain" else _verdict(rows, _row_id(key["salt"], row), abstained)
        if row["output"].get("kind") == "explain":
            if verdict and all(verdict[criterion] == "pass" for criterion in CRITERIA):
                bucket["explanation_passes"] += 1
                if row["label"] == "explanation_required":
                    bucket["all_six_on_explanation_required"] += 1
        elif row["label"] == "abstention_accepted" and row["abstention_fits"] and verdict and verdict.get("abstention") == "pass":
            bucket["abstention_passes"] += 1
    preferences = {"model": 0, "template": 0, "tie": 0}
    for case, choice in pairs.items():
        if not isinstance(choice, str):
            raise IncompleteReview("A paired judgment must be a row id or tie.")
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
