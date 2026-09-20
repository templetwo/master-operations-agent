"""Durable development comparison. Labels never enter the provider context."""

import json
import platform
from pathlib import Path
import subprocess
import sys

from .contracts import Rejected, canonical, digest, stamp
from .drills import evaluate_drills, MANIFEST_PATH
from .engine import ENTRY, SYSTEM
from .evidence import EvidenceStore
from .knowledge import POLICY_HASH
from .providers import Baseline, Ollama

ROOT = Path(__file__).resolve().parents[1]


class AlwaysRefuse:
    name = "always-refuse-negative-control"

    def respond(self, messages):
        return {"kind": "abstain", "reason": "insufficient_evidence"}


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def source_hashes():
    import hashlib
    files = {}
    for pattern in ("moa/**/*.py", "moa/web/*", "moa/data/*.json", "scripts/*", "tests/*.py", "pyproject.toml"):
        for path in sorted(ROOT.glob(pattern)):
            if path.is_file(): files[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def hardware():
    result = {"system": platform.system(), "release": platform.release(), "machine": platform.machine(), "python": sys.version}
    if platform.system() == "Darwin":
        try:
            response = subprocess.run(["sysctl", "-n", "hw.memsize", "machdep.cpu.brand_string"],
                                      check=True, capture_output=True, text=True, timeout=5)
            memory, cpu = response.stdout.strip().splitlines()
            result.update(memory_bytes=int(memory), cpu=cpu)
        except (OSError, ValueError, subprocess.SubprocessError):
            result["hardware_details"] = "UNVERIFIED: hardware query unavailable"
    return result


def pair_reports(baseline, candidate, control):
    rows = []
    for report in (candidate, control):
        match = (len(baseline["cases"]) == len(report["cases"]) and all(
            a["id"] == b["id"] and a["expected"] == b["expected"] and
            a["process_data_sha256"] == b["process_data_sha256"]
            for a, b in zip(baseline["cases"], report["cases"])))
        rows.append({"provider": report["provider"], "matched": match})
    return rows


def inference_metrics(report):
    calls = [event["payload"]["data"] for event in report["evidence"]["events"] if event["payload"]["kind"] == "provider_call"]
    durations = [call["wall_ms"] for call in calls]
    # Missing or malformed server counters remain unavailable, never zero tokens.
    counters = {}
    for field in ("prompt_eval_count", "eval_count", "eval_duration", "load_duration"):
        values = [call.get("reported", {}).get(field) for call in calls]
        counters[field] = sum(values) if values and all(type(v) is int and v >= 0 for v in values) else None
    return {"calls": len(calls), "call_wall_ms_total": round(sum(durations), 2),
            "call_wall_ms_max": max(durations, default=None), "server_reported_totals": counters,
            "time_to_first_token": "UNMEASURED: non-streaming requests",
            "warmup_included": False}


def compare(sim_repo, model, expected_digest, output, port=11434, progress=None):
    provider = Ollama(model, port, expected_digest=expected_digest)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(MANIFEST_PATH.read_text())
    config = {"started_at": stamp(), "scope": "synthetic-development-only", "promotion": "not_evaluated",
              "model": model, "expected_digest": expected_digest, "manifest_sha256": digest(manifest),
              "policy_sha256": POLICY_HASH, "system_prompt_sha256": digest(SYSTEM),
              "entry_message_sha256": digest(ENTRY),
              "source_sha256": source_hashes(), "hardware": hardware(),
              "freshness": "Each provider receives independently regenerated fresh observations; timestamps are never renewed.",
              "pairing": "Compare process data excluding capture times, snapshot IDs and epoch IDs; record original inputs separately.",
              "order": ["baseline", "always-refuse", "local-model"],
              "limits": "Development cases, two seeds, one pass, no held-out estimate or controls review. Daemon identity and isolation are trusted."}
    write_json(output / "run.json", dict(config, status="preparing"))
    try:
        config["server_version"] = provider.request("GET", "/api/version")
        loaded = provider.request("GET", "/api/ps")
        # Record loaded names/digests only, excluding unrelated daemon metadata.
        config["loaded_before"] = [{k: m[k] for k in ("name", "digest") if k in m} for m in loaded.get("models", [])]
        config["artifact"] = provider.prepare()
        write_json(output / "run.json", dict(config, status="running"))
        reports = {}
        for label, active in (("baseline", Baseline()), ("always-refuse", AlwaysRefuse()), ("local-model", provider)):
            if label == "local-model":
                warmup = {"purpose": "One explicit schema/protocol warmup before capturing scored observations; not a scored case."}
                try:
                    warmup["response"] = provider.respond([{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": canonical(ENTRY)}])
                except Rejected as exc:
                    warmup["error"] = exc.code
                warmup["calls"] = provider.drain_receipts()
                write_json(output / "warmup.json", warmup)
            store = EvidenceStore(output / (label + ".sqlite3"))
            try:
                def checkpoint(row):
                    with (output / (label + ".progress.jsonl")).open("a") as file:
                        file.write(canonical(row) + "\n")
                    if progress: progress(label, row)
                reports[label] = evaluate_drills(sim_repo, active, store, checkpoint)
                write_json(output / (label + ".json"), reports[label])
            finally:
                store.close()
        config["artifact_after"] = provider.prepare()
        config["server_version_after"] = provider.request("GET", "/api/version")
        pairings = pair_reports(reports["baseline"], reports["local-model"], reports["always-refuse"])
        integrity = {"paired_process_data": all(p["matched"] for p in pairings),
                     "source_unchanged": config["source_sha256"] == source_hashes(),
                     "artifact_metadata_unchanged": config["artifact"] == config["artifact_after"],
                     "server_version_unchanged": config["server_version"] == config["server_version_after"]}
        negative_control = not reports["always-refuse"]["passed"] and reports["always-refuse"]["metrics"]["useful_assessment"]["passed"] == 0
        valid = all(integrity.values()) and reports["baseline"]["passed"] and negative_control
        summary = {"finished_at": stamp(), "completed": True, "comparison_valid": valid, "promotion": "not_evaluated",
                   "local_passed_development": valid and reports["local-model"]["passed"], "integrity": integrity, "pairings": pairings,
                   "reports": {k: {"file": k + ".json", "passed": v["passed"], "metrics": v["metrics"],
                                   "evidence_anchor": v["evidence"]["anchor"]} for k, v in reports.items()},
                   "inference": inference_metrics(reports["local-model"])}
        write_json(output / "comparison.json", summary)
        write_json(output / "run.json", dict(config, status="completed", finished_at=summary["finished_at"]))
        return summary
    except Exception as exc:
        write_json(output / "run.json", dict(config, status="interrupted", error_type=type(exc).__name__))
        raise
