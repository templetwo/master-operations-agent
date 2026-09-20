"""Preregistered synthetic-only factorial guidance experiment. No promotion."""

import hashlib
import json
from pathlib import Path

from .cloud_comparison import cloud_metrics
from .comparison import AlwaysRefuse, pair_reports, source_hashes, write_json
from .contracts import canonical, digest, stamp
from .deepseek import DeepSeek, read_api_key
from .drills import MANIFEST_PATH, boundary_cases, build_cases, evaluate_drills, score_case, summarize_rows
from .engine import Agent, ENTRY, SYSTEM
from .evidence import EvidenceStore
from .guidance import OUTPUT_CONTRACT_GUIDANCE, POLICY_GUIDANCE
from .knowledge import POLICY_HASH
from .providers import Baseline

ARMS = ("unchanged", "output-only", "policy-only", "both")


def prompts():
    return {"unchanged": SYSTEM,
            "output-only": SYSTEM + "\n" + OUTPUT_CONTRACT_GUIDANCE,
            "policy-only": SYSTEM + "\n" + POLICY_GUIDANCE,
            "both": SYSTEM + "\n" + OUTPUT_CONTRACT_GUIDANCE + "\n" + POLICY_GUIDANCE}


def design():
    manifest = json.loads(MANIFEST_PATH.read_text())
    return {"schema": "moa-guidance-experiment-v1", "scope": "synthetic-development-only",
            "arms": list(ARMS), "prompts": prompts(),
            "prompt_sha256": {k: digest(v) for k, v in prompts().items()},
            "entry_message_sha256": digest(ENTRY), "policy_sha256": POLICY_HASH,
            "manifest_sha256": digest(manifest), "simulator_revision": manifest["simulator_revision"],
            "settings": {"model": "deepseek-flash", "temperature": 0, "max_tokens": 768,
                         "thinking": {"type": "disabled"}, "response_format": {"type": "json_object"}, "stream": False},
            "case_order": "Existing manifest order, then six boundary cases; rotate four-arm order left by case index modulo four.",
            "denominators": {"arms": 4, "usable_per_arm": 10, "guards_per_arm": 8, "repetitions": 1},
            "maximum_completion_calls": 244, "completion_cap_per_arm_including_warmup": 61,
            "primary": "Accepted usable advisories out of ten, separately for each arm. Report paired differences from unchanged.",
            "secondary": "Stage-specific failures, read completion, offline finding/check coverage and extras, latency and usage.",
            "decision": "Report every arm. No automatic model/prompt promotion and no repeated tuning within this preregistration.",
            "stop_rule": "Stop on setup, transport, authentication or model-identity failures. Count delivered malformed/truncated output from the confirmed alias as a failed case and continue. Save interrupted progress without a completed comparison claim.",
            "limits": "One small reused development set. Not a holdout, statistical efficacy claim, or engineer review. Cloud alias and service timing are mutable. Rotated order mitigates but cannot eliminate service drift."}


def register(path):
    path = Path(path)
    if path.exists():
        raise FileExistsError("Preregistration already exists; use a new path.")
    value = {"registered_at": stamp(), "design": design(), "source_sha256": source_hashes()}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as file:
        file.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _case_stream(sim_repo, manifest):
    yield from build_cases(sim_repo, manifest)
    first = dict(manifest, seeds=manifest["seeds"][:1], cases=manifest["cases"][:1])
    fresh = next(build_cases(sim_repo, first))["observation"]
    yield from boundary_cases(fresh)


def provider_failure_requires_stop(result, events):
    category = result.get("failure", {}).get("category")
    if category == "provider_preparation":
        return True
    if category != "provider_response":
        return False
    if result["reason"] in {"model_changed", "provider_http_error", "provider_scope", "model_unavailable"}:
        return True
    calls = [e["payload"]["data"] for e in events
             if e["payload"]["run_id"] == result["run_id"] and e["payload"]["kind"] == "provider_call"]
    # A received response from the expected alias can still have invalid content
    # or hit the output cap. Count that failure rather than selecting it away.
    return not (calls and calls[-1].get("response_sha256") and
                calls[-1].get("reported", {}).get("model") in {"deepseek-flash", "deepseek-v4.1-flash"})


def run(sim_repo, env_file, output, preregistration, expected_sha256, *, allow_cloud_synthetic=False, progress=None):
    if allow_cloud_synthetic is not True:
        raise ValueError("Explicit synthetic-cloud consent is required.")
    raw = Path(preregistration).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Preregistration hash mismatch.")
    registered = json.loads(raw)
    if registered.get("design") != design() or registered.get("source_sha256") != source_hashes():
        raise ValueError("Code or experiment design differs from preregistration.")
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Use a new experiment output directory.")
    key = read_api_key(env_file)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "preregistration.json", registered)
    config = {"started_at": stamp(), "status": "preparing", "scope": "synthetic-development-only",
              "preregistration_sha256": expected_sha256, "source_sha256": registered["source_sha256"],
              "promotion": "not_evaluated", "credential": "Explicit dotenv value read in memory, not recorded."}
    write_json(output / "run.json", config)
    stores, reports, providers = {}, {}, {}
    try:
        # Controls use the same cases, independent of candidate inference.
        for label, provider in (("baseline", Baseline()), ("always-refuse", AlwaysRefuse())):
            with_store = EvidenceStore(output / (label + ".sqlite3"))
            try:
                reports[label] = evaluate_drills(sim_repo, provider, with_store)
                write_json(output / (label + ".json"), reports[label])
            finally:
                with_store.close()
        control = reports["always-refuse"]
        if (not reports["baseline"]["passed"] or control["passed"]
                or control["metrics"]["useful_assessment"] != {"passed": 0, "total": 10}
                or control["metrics"]["input_guards"] != {"passed": 8, "total": 8}):
            raise ValueError("Control prerequisites failed before cloud inference.")
        chosen_prompts = prompts()
        for arm in ARMS:
            provider = DeepSeek(key, allow_cloud_synthetic=True)
            providers[arm] = provider
            metadata = provider.prepare()
            warmup = {"metadata": metadata, "purpose": "Unscored synthetic protocol warmup."}
            try:
                warmup["response"] = provider.respond([{"role": "system", "content": chosen_prompts[arm]},
                                                       {"role": "user", "content": canonical(ENTRY)}])
            finally:
                warmup["calls"] = provider.drain_receipts()
                write_json(output / (arm + ".warmup.json"), warmup)
            stores[arm] = EvidenceStore(output / (arm + ".sqlite3"))
        config["status"] = "running"
        write_json(output / "run.json", config)
        manifest = json.loads(MANIFEST_PATH.read_text())
        rows = {arm: [] for arm in ARMS}
        streams = {arm: iter(_case_stream(sim_repo, manifest)) for arm in ARMS}
        agents = {arm: Agent(stores[arm], providers[arm], system_prompt=chosen_prompts[arm]) for arm in ARMS}
        total = len(reports["baseline"]["cases"])
        for index in range(total):
            order = ARMS[index % 4:] + ARMS[:index % 4]
            for arm in order:
                case = next(streams[arm])
                result = agents[arm].assess(case["observation"])
                row = score_case(case, result)
                rows[arm].append(row)
                with (output / "progress.jsonl").open("a") as file:
                    file.write(canonical({"case_index": index, "arm": arm, "row": row}) + "\n")
                if progress:
                    progress(arm, row)
                if result.get("failure", {}).get("category") in {"provider_preparation", "provider_response"} and provider_failure_requires_stop(result, stores[arm].export()):
                    raise ValueError("Provider failure interrupted the experiment; inspect recorded events.")
        for arm in ARMS:
            if next(streams[arm], None) is not None:
                raise ValueError("Unexpected case count.")
            reports[arm] = {"suite": manifest["suite"], "split": "development", "review_status": manifest["review_status"],
                            "manifest_sha256": digest(manifest), "provider": providers[arm].name,
                            "arm": arm, "system_prompt_sha256": digest(chosen_prompts[arm]),
                            "passed": all(r["passed"] for r in rows[arm]), "metrics": summarize_rows(rows[arm]),
                            "cases": rows[arm], "limits": manifest["limits"], "evidence": stores[arm].bundle()}
            write_json(output / (arm + ".json"), reports[arm])
        pairings = {arm: pair_reports(reports["baseline"], reports[arm], reports["always-refuse"]) for arm in ARMS}
        listings = {arm: providers[arm].inspect_models() for arm in ARMS}
        integrity = {"source_unchanged": registered["source_sha256"] == source_hashes(),
                     "paired_process_data": all(p["matched"] for pairs in pairings.values() for p in pairs),
                     "aliases_listed_after": all(x["listed"] for x in listings.values()),
                     "controls_passed": reports["baseline"]["passed"] and not reports["always-refuse"]["passed"]
                         and reports["always-refuse"]["metrics"]["input_guards"] == {"passed": 8, "total": 8}}
        reference = reports["unchanged"]["metrics"]["useful_assessment"]["passed"]
        summary = {"completed": True, "finished_at": stamp(), "experiment_valid": all(integrity.values()),
                   "integrity": integrity, "pairings": pairings, "promotion": "not_evaluated",
                   "arms": {arm: {"metrics": reports[arm]["metrics"], "inference": cloud_metrics(reports[arm]),
                                   "accepted_case_difference_from_unchanged": reports[arm]["metrics"]["useful_assessment"]["passed"] - reference,
                                   "evidence_anchor": reports[arm]["evidence"]["anchor"]} for arm in ARMS},
                   "limits": design()["limits"]}
        write_json(output / "comparison.json", summary)
        config.update(status="completed", finished_at=summary["finished_at"])
        write_json(output / "run.json", config)
        return summary
    except Exception as exc:
        config.update(status="interrupted", error_type=type(exc).__name__, error_code=getattr(exc, "code", "execution_error"))
        for arm, store in stores.items():
            write_json(output / (arm + ".interrupted-evidence.json"), store.bundle())
        write_json(output / "run.json", config)
        raise
    finally:
        for store in stores.values():
            store.close()
