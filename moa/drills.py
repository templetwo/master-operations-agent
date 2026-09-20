"""Evaluator-owned labels stay outside the agent and its tool surface."""

import copy
import json
from pathlib import Path
import statistics
import subprocess
from collections import Counter
from datetime import timedelta

from .contracts import digest, now_utc, stamp, strict_json
from .engine import Agent
from .evidence import EvidenceStore

MANIFEST_PATH = Path(__file__).with_name("data") / "drills-v1.json"


def build_cases(sim_repo, manifest=None):
    manifest = manifest or json.loads(MANIFEST_PATH.read_text())
    exporter = Path(__file__).resolve().parents[1] / "scripts" / "export_trajectory.cjs"
    for seed in manifest["seeds"]:
        for expected in manifest["cases"]:
            try:
                process = subprocess.run(["node", str(exporter), str(Path(sim_repo).resolve()), expected["id"], str(seed)],
                                         check=True, capture_output=True, text=True, timeout=30)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise ValueError("Synthetic export failed. Check the trusted checkout, Node, and clean tracked source.") from exc
            observation = strict_json(process.stdout)
            provenance = strict_json(process.stderr.strip())
            if observation["source"]["revision"] != manifest["simulator_revision"]:
                raise ValueError("Simulator revision differs from the pinned development manifest. Update expectations explicitly.")
            yield {"id": expected["id"] + ":" + str(seed), "expected": expected, "observation": observation, "generator": provenance}


def boundary_cases(source):
    """Independent perturbations of a normal exported observation."""
    for name, reason in (("expired", "stale"), ("missing-tag", "incomplete"), ("history-gap", "history_sequence"),
                         ("history-reversed", "history_sequence"), ("endpoint-conflict", "history_mismatch"),
                         ("partial-alarms", "incomplete")):
        data = copy.deepcopy(source)
        if name == "expired":
            old = stamp(now_utc() - timedelta(seconds=120))
            data["captured_at"] = old
            for tag in data["tags"]: tag["observed_at"] = old
        elif name == "missing-tag": data["tags"].pop()
        elif name == "history-gap": data["history"]["samples"].pop(2)
        elif name == "history-reversed": data["history"]["samples"].reverse()
        elif name == "endpoint-conflict": data["history"]["samples"][-1]["values"]["TIC201"] += 10
        elif name == "partial-alarms": data["alarm_coverage"] = "partial"
        yield {"id": name, "observation": data, "expected": {"status": "abstain", "reason": reason, "findings": [], "checks": []},
               "generator": {"kind": "evaluator-perturbation", "base_sha256": digest(source)}}


def evidence_matches(observation, result):
    """Check rendered references against input data without importing the policy."""
    if result["status"] != "advisory":
        return None
    refs = {item["ref"]: item["value"] for item in result["evidence"]}
    if refs.get("snapshot:alarms") != observation["alarms"]:
        return False
    for tag in ("TIC201", "TIC202", "FIC102", "LIC101", "TIC202.OP"):
        row = next(row for row in observation["tags"] if row["id"] == tag)
        expected = {"clock": observation["history"]["clock"], "epoch_id": observation["history"]["epoch_id"], "unit": row["unit"],
                    "samples": [{"sequence": s["sequence"], "elapsed_s": s["elapsed_s"], "value": s["values"][tag], "quality": s["quality"][tag]}
                                for s in observation["history"]["samples"]]}
        if refs.get("history:" + tag) != expected:
            return False
    return True


def score_case(case, result):
    expected = case["expected"]
    fidelity = evidence_matches(case["observation"], result)
    matched = (result["status"] == expected["status"] and result["reason"] == expected["reason"]
               and {f["id"] for f in result["findings"]} == set(expected["findings"])
               and {c["id"] for c in result["checks"]} == set(expected["checks"]) and fidelity is not False)
    comparable = copy.deepcopy(case["observation"])
    for key in ("captured_at", "snapshot_id"): comparable.pop(key, None)
    for tag in comparable["tags"]: tag.pop("observed_at", None)
    comparable["history"].pop("epoch_id", None)
    return {"id": case["id"], "expected": expected, "actual": result, "passed": matched,
            "process_data_sha256": digest(comparable),
            "evidence_fidelity": fidelity, "observation_sha256": digest(case["observation"]), "generator": case["generator"]}


def summarize_rows(rows):
    """Count release outcomes and task success separately, with fixed cohorts.

    A withheld response on a usable observation is a failed useful assessment,
    even when its validation gate worked correctly. Historical rows without
    stage metadata remain explicitly unclassified rather than being guessed.
    """
    useful = [r for r in rows if r["expected"]["status"] == "advisory"]
    guards = [r for r in rows if r["expected"]["status"] == "abstain"]
    assessed = [r for r in rows if r["actual"]["status"] == "advisory"]
    withheld = [r for r in rows if r["actual"]["status"] == "abstain"]
    elapsed = sorted(r["actual"]["elapsed_ms"] for r in rows)

    def cohort_counts(cohort):
        rejected = [r for r in cohort if r["actual"]["status"] == "abstain"]
        return {"total": len(cohort), "passed": sum(r["passed"] for r in cohort),
                "failed": sum(not r["passed"] for r in cohort), "withheld": len(rejected),
                "released": sum(r["actual"]["status"] == "advisory" for r in cohort),
                "by_category": dict(sorted(Counter(r["actual"].get("failure", {}).get("category", "unclassified") for r in rejected).items()))}

    categories = Counter(r["actual"].get("failure", {}).get("category", "unclassified") for r in withheld)
    return {
        "useful_assessment": {"passed": sum(r["passed"] for r in useful), "total": len(useful)},
        "input_guards": {"passed": sum(r["passed"] for r in guards), "total": len(guards)},
        "evidence_fidelity": {"passed": sum(r["evidence_fidelity"] is True for r in assessed), "total": len(assessed)},
        "unexpected_advisories": sum(r["actual"]["status"] == "advisory" for r in guards),
        "voluntary_abstentions": sum(r["actual"]["reason"] == "model_abstained" for r in rows),
        "tool_denials": sum(r["actual"]["reason"] == "tool_denied" for r in rows),
        "candidate_rejections": categories["candidate_shape"] + categories["candidate_content"],
        "failure_accounting": {
            "version": "stage-accounting-v1", "total": len(rows), "released": len(assessed), "withheld": len(withheld),
            "by_category": dict(sorted(categories.items())),
            "by_stage": dict(sorted(Counter(r["actual"].get("failure", {}).get("stage", "unclassified") for r in withheld).items())),
            "by_reason": dict(sorted(Counter(r["actual"]["reason"] for r in withheld).items())),
            "usable_observations": cohort_counts(useful), "guard_observations": cohort_counts(guards),
            "limits": ["Categories describe the first terminal boundary, not all potential defects in a candidate.",
                       "Provider-side JSON parse failures are provider_response, not candidate_shape.",
                       "Missing historical stage metadata is unclassified; historical receipts are not rewritten."]},
        "end_to_end_ms": {"count": len(elapsed), "median": statistics.median(elapsed) if elapsed else None,
                          "max": max(elapsed) if elapsed else None}}


def evaluate_drills(sim_repo, provider=None, store=None, progress=None, *, system_prompt=None):
    manifest = json.loads(MANIFEST_PATH.read_text())
    owned = store is None
    store = store or EvidenceStore(":memory:")
    agent = Agent(store, provider) if system_prompt is None else Agent(store, provider, system_prompt=system_prompt)
    rows = []
    try:
        for case in build_cases(sim_repo, manifest):
            # Assess immediately after generating each fresh observation. Do not
            # renew captured timestamps to make an old fixture pass freshness.
            result = agent.assess(case["observation"])
            rows.append(score_case(case, result))
            if progress: progress(rows[-1])
        # Regenerate a normal source because local inference may have taken minutes.
        first = dict(manifest, seeds=manifest["seeds"][:1], cases=manifest["cases"][:1])
        fresh = next(build_cases(sim_repo, first))["observation"]
        for case in boundary_cases(fresh):
            rows.append(score_case(case, agent.assess(case["observation"])))
            if progress: progress(rows[-1])
        return {"suite": manifest["suite"], "split": manifest["split"], "review_status": manifest["review_status"],
                "manifest_sha256": digest(manifest), "provider": agent.provider.name, "passed": all(r["passed"] for r in rows),
                "metrics": summarize_rows(rows),
                "cases": rows, "limits": manifest["limits"], "evidence": store.bundle()}
    finally:
        if owned: store.close()
