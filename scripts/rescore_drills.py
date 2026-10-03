#!/usr/bin/env python3
"""Score a development drill manifest against a trusted simulator checkout.

Deterministic providers only (the baseline or the always-refuse negative
control); no model is called. A checkout at a revision the
manifest was not written for is refused unless --allow-revision-mismatch is
given, and then the override is recorded in the output. The manifest file is
never written. --compare checks the rows against a recorded receipt.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from moa.comparison import AlwaysRefuse  # noqa: E402
from moa.contracts import digest, now_utc, stamp  # noqa: E402
from moa.drills import evaluate_drills  # noqa: E402
from moa.providers import Baseline  # noqa: E402

PROVIDERS = {"baseline": Baseline, "always-refuse": AlwaysRefuse}
OVERRIDE_NOTE = "Expectations applied unchanged to a revision they were not written for. A miss is reported, not absorbed."
COMPARED = ("passed", "expected.status", "expected.reason", "expected.findings",
            "actual.status", "actual.reason", "actual.findings", "process_data_sha256", "evidence_fidelity")


def effective_manifest(manifest, revision, allow_mismatch):
    if manifest["simulator_revision"] == revision:
        return manifest, None
    if not allow_mismatch:
        raise ValueError("Simulator checkout is not at the manifest pin. Pass --allow-revision-mismatch to score it anyway.")
    scored = copy.deepcopy(manifest)
    scored["simulator_revision"] = revision
    return scored, {"pinned_revision": manifest["simulator_revision"], "scored_revision": revision, "note": OVERRIDE_NOTE}


def receipt_rows(cases):
    """Keep identifiers and hashes; drop rendered catalog text and evidence values."""
    return [{"id": row["id"], "passed": row["passed"],
             "expected": {key: row["expected"][key] for key in ("status", "reason", "findings", "checks")},
             "actual": {"status": row["actual"]["status"], "reason": row["actual"]["reason"],
                        "findings": [item["id"] for item in row["actual"]["findings"]],
                        "checks": [item["id"] for item in row["actual"]["checks"]]},
             "process_data_sha256": row["process_data_sha256"], "observation_sha256": row["observation_sha256"],
             "evidence_fidelity": row["evidence_fidelity"]} for row in cases]


def _field(row, path):
    value = row
    for key in path.split("."):
        value = value.get(key) if isinstance(value, dict) else None
    return sorted(value) if isinstance(value, list) else value


def compare_rows(rows, recorded):
    """Name every compared field that differs from a recorded receipt, row by row."""
    ours = {row["id"]: row for row in rows}
    mismatches = []
    for old in recorded:
        new = ours.pop(old["id"], None)
        if new is None:
            mismatches.append({"id": old["id"], "field": "id", "recorded": old["id"], "actual": None})
            continue
        for path in COMPARED:
            if _field(old, path) != _field(new, path):
                mismatches.append({"id": old["id"], "field": path, "recorded": _field(old, path), "actual": _field(new, path)})
    mismatches += [{"id": key, "field": "id", "recorded": None, "actual": key} for key in ours]
    return mismatches


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sim_repo", type=Path, help="Trusted local simulator checkout with clean tracked source")
    parser.add_argument("--manifest", type=Path, default=Path("moa/data/drills-v1.json"))
    parser.add_argument("--provider", choices=sorted(PROVIDERS), default="baseline")
    parser.add_argument("--allow-revision-mismatch", action="store_true")
    parser.add_argument("--compare", type=Path, help="Recorded receipt whose 'cases' rows are checked")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest_bytes = (ROOT / args.manifest).read_bytes()
    revision = subprocess.run(["git", "-C", str(args.sim_repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    try:
        manifest, override = effective_manifest(json.loads(manifest_bytes), revision, args.allow_revision_mismatch)
    except ValueError as exc:
        parser.error(str(exc))
    report = evaluate_drills(args.sim_repo, PROVIDERS[args.provider](), manifest=manifest)
    rows = receipt_rows(report["cases"])
    comparison = None
    if args.compare:
        receipt_bytes = (ROOT / args.compare).read_bytes()
        comparison = {"receipt": str(args.compare), "sha256": hashlib.sha256(receipt_bytes).hexdigest(),
                      "compared_fields": list(COMPARED), "mismatches": compare_rows(rows, json.loads(receipt_bytes)["cases"])}
    output = {"schema": "moa-drills-rescore-v1", "recorded_at": stamp(now_utc()), "provider": report["provider"], "models_called": 0,
              "manifest": {"path": str(args.manifest), "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                           "suite": manifest["suite"], "pinned_revision": json.loads(manifest_bytes)["simulator_revision"]},
              "scored_revision": revision, "revision_override": override, "passed": report["passed"],
              "metrics": report["metrics"], "cases": rows, "evidence_bundle_sha256": digest(report["evidence"]),
              "limits": report["limits"], "comparison": comparison}
    args.out.write_text(json.dumps(output, indent=1) + "\n")
    useful, guards = report["metrics"]["useful_assessment"], report["metrics"]["input_guards"]
    print(f"{manifest['suite']} at {revision[:7]}: useful {useful['passed']}/{useful['total']}, guards {guards['passed']}/{guards['total']}"
          + (f", {len(comparison['mismatches'])} mismatches against {args.compare}" if comparison else ""), file=sys.stderr)
    return 1 if comparison and comparison["mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
