"""Explicit cloud comparison of generated synthetic drills, never imported data."""

import json
from pathlib import Path

from .comparison import AlwaysRefuse, pair_reports, source_hashes, write_json
from .contracts import canonical, digest, stamp
from .deepseek import DeepSeek, read_api_key
from .drills import MANIFEST_PATH, evaluate_drills
from .engine import ENTRY, SYSTEM
from .evidence import EvidenceStore
from .knowledge import POLICY_HASH
from .providers import Baseline


def cloud_metrics(report):
    calls = [e["payload"]["data"] for e in report["evidence"]["events"] if e["payload"]["kind"] == "provider_call"]
    usage = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
        values = [c.get("reported", {}).get("usage", {}).get(key)
                  if isinstance(c.get("reported", {}).get("usage"), dict) else None for c in calls]
        usage[key] = sum(values) if values and all(type(v) is int and v >= 0 for v in values) else None
    return {"calls": len(calls), "reported_usage": usage,
            "reported_models": sorted({c["reported"]["model"] for c in calls if isinstance(c.get("reported", {}).get("model"), str)}),
            "call_wall_ms_total": round(sum(c["wall_ms"] for c in calls), 2),
            "warmup_included": False, "time_to_first_token": "UNMEASURED: non-streaming requests",
            "cost": "Not inferred from tokens. Consult the provider bill for actual charges."}


def compare_deepseek(sim_repo, env_file, output, *, allow_cloud_synthetic=False, progress=None):
    if allow_cloud_synthetic is not True:
        raise ValueError("Pass --allow-cloud-synthetic to send generated lab data to DeepSeek.")
    output = Path(output).resolve()
    if output.exists(): raise FileExistsError("Use a new comparison output directory.")
    provider = DeepSeek(read_api_key(env_file), allow_cloud_synthetic=True)
    output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(MANIFEST_PATH.read_text())
    config = {"started_at": stamp(), "scope": "explicit-cloud-synthetic-comparison", "promotion": "not_evaluated",
              "provider": provider.name, "credential": "Explicit dotenv DEEPSEEK_API_KEY; value and file contents not recorded.",
              "model_documentation": {"version": "DeepSeek-V4.1-Flash", "alias": "deepseek-flash",
                                      "url": "https://api-docs.deepseek.com/quick_start/pricing/", "read_date": "2026-09-20"},
              "source_sha256": source_hashes(), "manifest_sha256": digest(manifest), "policy_sha256": POLICY_HASH,
              "system_prompt_sha256": digest(SYSTEM), "entry_message_sha256": digest(ENTRY),
              "order": ["baseline", "always-refuse", "cloud-model"],
              "limits": "Generated synthetic development cases only. Mutable cloud alias, no weight pin. JSON mode differs from local schema-constrained decoding. No held-out score or controls review.",
              "freshness": "New simulator captures per case; unchanged 60-second freshness limit."}
    write_json(output / "run.json", dict(config, status="preparing"))
    try:
        config["provider_metadata"] = provider.prepare()
        # Probe availability/protocol before committing to scored inference.
        warmup = {"purpose": "One synthetic protocol request, no plant data or process observation."}
        try:
            warmup["response"] = provider.respond([{"role": "system", "content": SYSTEM}, {"role": "user", "content": canonical(ENTRY)}])
        finally:
            warmup["calls"] = provider.drain_receipts()
            write_json(output / "warmup.json", warmup)
        write_json(output / "run.json", dict(config, status="running"))
        reports = {}
        for label, active in (("baseline", Baseline()), ("always-refuse", AlwaysRefuse()), ("cloud-model", provider)):
            store = EvidenceStore(output / (label + ".sqlite3"))
            try:
                def checkpoint(row):
                    with (output / (label + ".progress.jsonl")).open("a") as file: file.write(canonical(row) + "\n")
                    if progress: progress(label, row)
                reports[label] = evaluate_drills(sim_repo, active, store, checkpoint)
                write_json(output / (label + ".json"), reports[label])
            finally:
                store.close()
        config["model_listing_after"] = provider.inspect_models()
        pairings = pair_reports(reports["baseline"], reports["cloud-model"], reports["always-refuse"])
        integrity = {"paired_process_data": all(p["matched"] for p in pairings),
                     "source_unchanged": config["source_sha256"] == source_hashes(),
                     "requested_alias_still_listed": config["model_listing_after"]["listed"]}
        control = reports["always-refuse"]["metrics"]
        valid = (all(integrity.values()) and reports["baseline"]["passed"] and not reports["always-refuse"]["passed"]
                 and control["useful_assessment"]["passed"] == 0 and control["input_guards"]["passed"] == control["input_guards"]["total"])
        result = {"completed": True, "finished_at": stamp(), "comparison_valid": valid, "promotion": "not_evaluated",
                  "cloud_passed_development": valid and reports["cloud-model"]["passed"], "integrity": integrity, "pairings": pairings,
                  "reports": {label: {"file": label + ".json", "passed": r["passed"], "metrics": r["metrics"],
                                      "evidence_anchor": r["evidence"]["anchor"]} for label, r in reports.items()},
                  "inference": cloud_metrics(reports["cloud-model"])}
        write_json(output / "comparison.json", result)
        write_json(output / "run.json", dict(config, status="completed", finished_at=result["finished_at"]))
        return result
    except Exception as exc:
        write_json(output / "run.json", dict(config, status="interrupted", error_type=type(exc).__name__,
                                            error_code=getattr(exc, "code", "execution_error")))
        raise
