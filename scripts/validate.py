#!/usr/bin/env python3
"""Reproducible local validation with immutable run receipts."""
import argparse
import os
from pathlib import Path
import sys
from validation_v08 import DEFAULT_TIMEOUT_SECONDS, run_validation

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim-repo", help="Trusted local simulator checkout for integration tests")
    parser.add_argument("--output", help="New output directory; defaults to a unique receipts/validation-* directory")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Per-step timeout in seconds (default: 600)")
    parser.add_argument("--current-pointer", default="receipts/current.json", help="Explicit mutable index pointing to the newest validation receipt")
    args = parser.parse_args()
    output = ROOT / args.output if args.output else None
    env = dict(os.environ)
    if args.sim_repo: env["MOA_SIM_REPO"] = str(Path(args.sim_repo).resolve())
    commands = [[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                [sys.executable, "-m", "moa", "eval"],
                ["node", "--check", "moa/web/app.js"], ["node", "--check", "scripts/export_sim.cjs"],
                ["node", "--check", "scripts/export_trajectory.cjs"]]
    if args.sim_repo:
        commands.append([sys.executable, "-m", "moa", "drill-eval", "--sim-repo", str(Path(args.sim_repo).resolve())])
    receipt = run_validation(commands, root=ROOT, output=output, env=env, timeout=args.timeout,
                             current_pointer=ROOT / args.current_pointer,
                             metadata={"simulator_checkout": args.sim_repo})
    return 0 if receipt["passed"] else 1


if __name__ == "__main__": raise SystemExit(main())
