"""Offline receipt diagnostics, independent of engine, policy and release scoring.

Only the Python standard library is imported. Labels are authored expectations,
not independently established process truth. Nothing here authorizes advice.
"""

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


class DiagnosticError(ValueError):
    """The input cannot support a trustworthy offline comparison."""


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise DiagnosticError("Duplicate JSON key.")
            result[key] = value
        return result

    def constant(value):
        raise DiagnosticError("Non-finite JSON number.")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise DiagnosticError("Input is not strict finite JSON.") from exc


def _digest(value):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise DiagnosticError("Input contains a non-JSON value.") from exc
    return hashlib.sha256(encoded.encode()).hexdigest()


def verify_bundle(bundle):
    """Verify every link and the embedded head, not external authenticity."""
    if not isinstance(bundle, dict) or set(bundle) != {"anchor", "events"} or not isinstance(bundle["events"], list):
        raise DiagnosticError("Expected a full evidence bundle.")
    previous = "0" * 64
    for number, event in enumerate(bundle["events"], 1):
        if not isinstance(event, dict) or set(event) != {"seq", "previous", "payload", "hash"}:
            raise DiagnosticError("Invalid evidence event shape.")
        payload = event["payload"]
        if (type(event["seq"]) is not int or event["seq"] != number or event["previous"] != previous
                or event["hash"] != _digest({key: event[key] for key in ("seq", "previous", "payload")})):
            raise DiagnosticError("Evidence chain integrity failure.")
        if (not isinstance(payload, dict) or set(payload) != {"run_id", "kind", "at", "data"}
                or not all(isinstance(payload[key], str) and payload[key] for key in ("run_id", "kind", "at"))):
            raise DiagnosticError("Invalid evidence payload shape.")
        previous = event["hash"]
    anchor = {"events": len(bundle["events"]), "head": previous}
    if bundle["anchor"] != anchor or type(bundle["anchor"].get("events")) is not int:
        raise DiagnosticError("Evidence anchor mismatch.")
    return anchor


def _ids(value, allow_empty=True):
    return (isinstance(value, list) and (allow_empty or bool(value))
            and all(isinstance(item, str) and item for item in value)
            and len(set(value)) == len(value))


def envelope(candidate):
    """Describe JSON envelope only, without reimplementing release decisions."""
    if not isinstance(candidate, dict):
        return {"valid": False, "issues": ["not_an_object"]}
    kind = candidate.get("kind")
    required = {"advice": {"kind", "finding_ids", "check_ids", "evidence"},
                "tool": {"kind", "name", "arguments"}, "abstain": {"kind", "reason"}}.get(kind) if isinstance(kind, str) else None
    if required is None:
        return {"valid": False, "issues": ["unknown_kind"]}
    issues = []
    if set(candidate) != required:
        issues.append("unexpected_or_missing_fields")
    if kind == "advice":
        for field in ("finding_ids", "check_ids", "evidence"):
            values = candidate.get(field)
            if not _ids(values, allow_empty=False) or len(values) > 16:
                issues.append(field + "_invalid")
    elif kind == "tool":
        if not isinstance(candidate.get("name"), str) or not isinstance(candidate.get("arguments"), dict):
            issues.append("invalid_tool_shape")
    elif candidate.get("reason") != "insufficient_evidence":
        issues.append("invalid_abstention_reason")
    return {"valid": not issues, "issues": issues}


def _offline_view(candidate):
    """Only two observed packaging changes; never repair content or IDs."""
    transformations = []
    if isinstance(candidate, dict) and set(candidate) == {"type", "content"} and candidate["type"] == "json_object" and isinstance(candidate["content"], dict):
        candidate = candidate["content"]
        transformations.append("unwrap_type_json_object_content")
    if isinstance(candidate, dict) and candidate.get("kind") == "advice" and candidate.get("type") == "json_object":
        candidate = {key: value for key, value in candidate.items() if key != "type"}
        transformations.append("remove_type_json_object")
    return candidate, transformations


def _field(candidate, field, expected):
    supplied = candidate.get(field) if isinstance(candidate, dict) and candidate.get("kind") == "advice" else None
    observed = isinstance(supplied, list) and all(isinstance(item, str) and item for item in supplied)
    predicted = set(supplied) if observed else set()
    target = set(expected)
    matched = target & predicted
    valid = _ids(supplied, allow_empty=False) and len(supplied) <= 16
    return {"prediction_observed": observed, "id_list_valid": valid,
            "expected_ids": sorted(target), "predicted_ids": sorted(predicted) if observed else None,
            "matched_ids": sorted(matched), "omitted_ids": sorted(target - predicted),
            "extra_ids": sorted(predicted - target) if observed else None,
            "matched": len(matched), "expected": len(target), "predicted": len(predicted),
            "recall": len(matched) / len(target) if target else None,
            "precision": len(matched) / len(predicted) if predicted else None,
            "exact_set": bool(valid and predicted == target)}


def _content(candidate, expected):
    return {"findings": _field(candidate, "finding_ids", expected["findings"]),
            "checks": _field(candidate, "check_ids", expected["checks"])}


def _summary(rows, view):
    useful = [row for row in rows if row["expected_status"] == "advisory"]
    result = {"cases": len(useful), "denominator": "All authored advisory cases, including absent or invalid candidates."}
    for field in ("findings", "checks"):
        values = [row[view]["content"][field] for row in useful]
        matched, expected, predicted = (sum(value[name] for value in values) for name in ("matched", "expected", "predicted"))
        result[field] = {"exact_sets": sum(value["exact_set"] for value in values), "total_cases": len(values),
                         "observed_id_lists": sum(value["prediction_observed"] for value in values),
                         "valid_id_lists": sum(value["id_list_valid"] for value in values),
                         "matched": matched, "expected": expected, "predicted": predicted,
                         "omitted": expected - matched, "extras": predicted - matched,
                         "micro_recall": matched / expected if expected else None,
                         "micro_precision": matched / predicted if predicted else None}
    return result


def diagnose_report(report):
    """Analyze an in-memory exported report. No network, policy or agent imports."""
    if not isinstance(report, dict) or not isinstance(report.get("cases"), list) or not report["cases"]:
        raise DiagnosticError("Expected a nonempty case report.")
    anchor = verify_bundle(report.get("evidence"))
    by_run = defaultdict(list)
    for event in report["evidence"]["events"]:
        by_run[event["payload"]["run_id"]].append(event)
    seen, case_ids, rows = set(), set(), []
    for case in report["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("actual"), dict) or not isinstance(case.get("expected"), dict):
            raise DiagnosticError("Invalid case shape.")
        actual, expected = case["actual"], case["expected"]
        run_id, case_id = actual.get("run_id"), case.get("id")
        if (not isinstance(run_id, str) or run_id in seen or run_id not in by_run
                or not isinstance(case_id, str) or case_id in case_ids):
            raise DiagnosticError("Cases must bind uniquely to evidence runs.")
        if (expected.get("status") not in ("advisory", "abstain")
                or not _ids(expected.get("findings")) or not _ids(expected.get("checks"))
                or (expected["status"] == "advisory" and (not expected["findings"] or not expected["checks"]))):
            raise DiagnosticError("Invalid explicit case expectations.")
        seen.add(run_id)
        case_ids.add(case_id)
        events = by_run[run_id]
        outcomes = [event for event in events if event["payload"]["kind"] == "outcome"]
        if len(outcomes) != 1 or events[-1] != outcomes[0]:
            raise DiagnosticError("Expected exactly one terminal outcome per run.")
        outcome = outcomes[0]
        if (outcome["payload"]["data"] != {key: value for key, value in actual.items() if key != "receipt"}
                or actual.get("receipt") != {"seq": outcome["seq"], "hash": outcome["hash"]}):
            raise DiagnosticError("Report result does not match its evidence outcome.")
        responses = [event for event in events if event["payload"]["kind"] == "provider_response"]
        candidate, sequence = None, None
        state = "absent"
        if responses:
            latest = responses[-1]
            if not isinstance(latest["payload"]["data"], dict) or "response" not in latest["payload"]["data"]:
                raise DiagnosticError("Malformed provider response event.")
            sequence = latest["seq"]
            candidate = latest["payload"]["data"]["response"]
            later_call = any(event["seq"] > sequence and event["payload"]["kind"] == "provider_call" for event in events)
            if later_call:
                candidate, state = None, "unparsed_later_provider_call"
            else:
                state = candidate.get("kind", "invalid_kind") if isinstance(candidate, dict) else "invalid_object"
                if not isinstance(state, str):
                    state = "invalid_kind"
        offline, transforms = _offline_view(candidate)
        row = {"id": case_id, "run_id": run_id, "expected_status": expected["status"],
               "original_release_status": actual.get("status"), "original_release_reason": actual.get("reason"),
               "original_case_passed": case.get("passed"), "candidate_state": state, "response_event_seq": sequence,
               "original": {"envelope": envelope(candidate), "content": _content(candidate, expected)},
               "offline_packaging_diagnostic": {"transformations": transforms, "envelope": envelope(offline),
                                                  "content": _content(offline, expected)}}
        rows.append(row)
    if seen != set(by_run):
        raise DiagnosticError("Evidence contains runs absent from case report.")
    return {"schema_version": "moa-offline-diagnostics-v1", "provider": report.get("provider"),
            "suite": report.get("suite"), "split": report.get("split"), "review_status": report.get("review_status"),
            "evidence_anchor": anchor, "integrity": "Full embedded chain verified; report outcomes bind to event hashes.",
            "expected_labels_sha256": _digest([{ "id": case["id"], "expected": case["expected"]} for case in report["cases"]]),
            "limits": ["Authored case labels are not independently reviewed ground truth and are outside the event chain.",
                       "An embedded hash-chain head does not attest authenticity or prevent whole-history replacement.",
                       "Content overlap is a diagnostic, never a release pass, safety score, or proof of comprehension.",
                       "Packaging transformations are offline only. Expected labels never enter a model request.",
                       "No evidence-reference correctness or process-truth validation is performed here.",
                       "Absent or invalid ID lists contribute zero matched/predicted IDs and all expected omissions; precision is undefined with no predictions."],
            "original_report_passed": report.get("passed"),
            "candidate_states": dict(sorted(Counter(row["candidate_state"] for row in rows).items())),
            "original_envelopes_valid": sum(row["original"]["envelope"]["valid"] for row in rows),
            "summary": {view: _summary(rows, view) for view in ("original", "offline_packaging_diagnostic")},
            "cases": rows}


def diagnose_file(source, output):
    """Create a new compact diagnostic with source-file hash, refusing overwrite."""
    source, output = Path(source), Path(output)
    raw = source.read_bytes()
    result = diagnose_report(_json(raw))
    result["input"] = {"path": str(source), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    result["diagnostic_source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(encoded)
    return result
