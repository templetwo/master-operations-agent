#!/usr/bin/env python3
"""Measure the unchanged disk-backed EvidenceStore append path, without providers."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import shlex
import sqlite3
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from moa.evidence import EvidenceStore


def source_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("moa/evidence.py", "moa/contracts.py", "scripts/profile_evidence.py")}


def profile(count, output):
    if type(count) is not int or count < 1:
        raise ValueError("count must be a positive integer")
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve the receipt before doing work. A prior attempt is never overwritten.
    receipt_file = output.open("x")
    progress = output.with_suffix(".progress.jsonl")
    measurements = []
    started = time.perf_counter()
    receipt = {"schema": "moa-evidence-profile-v1", "started_at": datetime.now(timezone.utc).isoformat(),
               "command": [sys.executable, *sys.argv], "shell_command": shlex.join([sys.executable, *sys.argv]),
               "cwd": str(Path.cwd()), "python": sys.version, "platform": platform.platform(),
               "sqlite_version": sqlite3.sqlite_version, "source_sha256": source_hashes(),
               "requested_appends": count, "measurements": measurements, "passed": False,
               "scope": "Disk-backed temporary SQLite database; unchanged EvidenceStore.append; small synthetic events. No model or plant. Not a streaming workload benchmark.",
               "payload_template": {"run_id": "profile-v08", "kind": "measurement", "data": {"index": "1..count", "value_milli": 12345}}}
    try:
        with progress.open("x") as journal, tempfile.TemporaryDirectory(prefix="moa-evidence-profile-") as directory:
            store = EvidenceStore(Path(directory) / "evidence.sqlite3")
            try:
                receipt["journal_mode"] = store.db.execute("PRAGMA journal_mode").fetchone()[0]
                receipt["synchronous"] = store.db.execute("PRAGMA synchronous").fetchone()[0]
                for index in range(1, count + 1):
                    before = time.perf_counter()
                    store.append("profile-v08", "measurement", {"index": index, "value_milli": 12345})
                    after = time.perf_counter()
                    row = {"append": index, "elapsed_seconds": after - before, "cumulative_seconds": after - started}
                    measurements.append(row)
                    journal.write(json.dumps(row) + "\n")
                    journal.flush()
                    if index % 1000 == 0 or index == count:
                        print(json.dumps(row), flush=True)
                before = time.perf_counter()
                receipt["anchor"] = store.verify()
                receipt["final_verify_seconds"] = time.perf_counter() - before
            finally:
                store.close()
        receipt["source_sha256_after"] = source_hashes()
        receipt["source_unchanged"] = receipt["source_sha256"] == receipt["source_sha256_after"]
        receipt["passed"] = len(measurements) == count and receipt["source_unchanged"]
    except BaseException as exc:
        receipt["error_type"] = type(exc).__name__
        raise
    finally:
        receipt["completed_appends"] = len(measurements)
        receipt["elapsed_seconds"] = time.perf_counter() - started
        receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
        json.dump(receipt, receipt_file, indent=2)
        receipt_file.write("\n")
        receipt_file.close()
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10000)
    parser.add_argument("--output", default="receipts/v0.8-slice/evidence-profile.json")
    args = parser.parse_args()
    return 0 if profile(args.count, args.output)["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
