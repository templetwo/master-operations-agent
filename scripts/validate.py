#!/usr/bin/env python3
"""Reproducible local validation with command output and source hashes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim-repo", help="Trusted local simulator checkout for integration tests")
    parser.add_argument("--output", default="receipts/latest")
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if args.sim_repo: env["MOA_SIM_REPO"] = str(Path(args.sim_repo).resolve())
    commands = [[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                [sys.executable, "-m", "moa", "eval"],
                ["node", "--check", "moa/web/app.js"], ["node", "--check", "scripts/export_sim.cjs"],
                ["node", "--check", "scripts/export_trajectory.cjs"]]
    if args.sim_repo:
        commands.append([sys.executable, "-m", "moa", "drill-eval", "--sim-repo", str(Path(args.sim_repo).resolve())])
    records = []
    for index, command in enumerate(commands):
        completed = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=120)
        stdout, stderr = f"check-{index + 1}.stdout", f"check-{index + 1}.stderr"
        (output / stdout).write_text(completed.stdout)
        (output / stderr).write_text(completed.stderr)
        records.append({"command": command, "exit_code": completed.returncode, "stdout": stdout, "stderr": stderr})
        print(f"{'PASS' if completed.returncode == 0 else 'FAIL'} {' '.join(command)}", flush=True)
    sources = {}
    for pattern in ("moa/**/*.py", "moa/web/*", "moa/data/*.json", "tests/*.py", "scripts/*", "pyproject.toml"):
        for file in ROOT.glob(pattern):
            if file.is_file(): sources[str(file.relative_to(ROOT))] = hashlib.sha256(file.read_bytes()).hexdigest()
    receipt = {"recorded_at": datetime.now(timezone.utc).isoformat(), "python": sys.version, "platform": platform.platform(),
               "simulator_checkout": args.sim_repo, "commands": records, "source_sha256": sources,
               "passed": all(r["exit_code"] == 0 for r in records),
               "scope": "Synthetic baseline and mocked provider validation. No actual model inference or plant connection."}
    (output / "validation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return 0 if receipt["passed"] else 1


if __name__ == "__main__": raise SystemExit(main())
