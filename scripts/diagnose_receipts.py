#!/usr/bin/env python3
"""Offline analysis only. Input receipts and release decisions remain unchanged."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from moa.diagnostics import DiagnosticError, diagnose_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Exported report JSON with full evidence chain")
    parser.add_argument("--output", required=True, help="New output JSON; existing files are refused")
    args = parser.parse_args()
    try:
        report = diagnose_file(args.input, args.output)
    except (DiagnosticError, OSError, RecursionError) as exc:
        print("Diagnostic not written: " + str(exc), file=sys.stderr)
        return 2
    summary = report["summary"]["offline_packaging_diagnostic"]
    print(f"Offline diagnostic written: {args.output}; {summary['cases']} authored advisory cases. Release decisions unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
