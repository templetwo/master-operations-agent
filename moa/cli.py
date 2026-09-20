import argparse
import json
import sqlite3
import sys
from pathlib import Path
from .contracts import Rejected, MAX_BYTES, strict_json
from .engine import Agent
from .evaluation import evaluate
from .evidence import EvidenceStore, EvidenceError
from .fixtures import SCENARIOS, fixture
from .providers import Baseline, Ollama


def emit(value):
    print(json.dumps(value, indent=2, allow_nan=False))


def read_json(path):
    with Path(path).open("rb") as file:
        return strict_json(file.read(MAX_BYTES + 1))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Master Operations Agent: synthetic research workbench")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Assess a fresh synthetic scenario")
    demo.add_argument("--scenario", choices=SCENARIOS, default="cooling")
    assess = sub.add_parser("assess", help="Assess a captured synthetic observation JSON file")
    assess.add_argument("observation")
    assess.add_argument("--task", default="assess_snapshot")
    fixtures = sub.add_parser("fixture", help="Print a fresh synthetic observation")
    fixtures.add_argument("--scenario", choices=SCENARIOS, default="cooling")
    evaluation = sub.add_parser("eval", help="Run public smoke scenarios and export receipts")
    drills = sub.add_parser("drill-eval", help="Run development trajectories from a trusted simulator checkout")
    drills.add_argument("--sim-repo", required=True)
    comparison = sub.add_parser("compare", help="Compare a pinned installed model with baseline and refusal control")
    comparison.add_argument("--sim-repo", required=True)
    comparison.add_argument("--model", required=True)
    comparison.add_argument("--expected-digest", required=True)
    comparison.add_argument("--output", required=True, help="New local receipt directory; existing directories are refused")
    comparison.add_argument("--ollama-port", type=int, default=11434)
    serve = sub.add_parser("serve", help="Open a loopback-only advisory workbench")
    serve.add_argument("--port", type=int, default=8765)
    verify = sub.add_parser("verify", help="Verify evidence integrity, optionally against an external anchor")
    verify.add_argument("--anchor", help="JSON file with events count and head hash")
    export = sub.add_parser("export", help="Export the evidence chain and external anchor")
    for command in (demo, assess, serve, verify, export):
        command.add_argument("--store", default=".moa/evidence.sqlite3")
    for command in (demo, assess, serve, evaluation, drills):
        command.add_argument("--model", help="Explicit installed Ollama name including tag. Otherwise use offline baseline.")
        command.add_argument("--ollama-port", type=int, default=11434)
    args = parser.parse_args(argv)
    store = None
    try:
        if args.command == "compare":
            from .comparison import compare
            report = compare(args.sim_repo, args.model, args.expected_digest, args.output, args.ollama_port,
                             lambda label, row: print(f"{label}: {row['id']}: {row['actual']['reason']} ({'PASS' if row['passed'] else 'FAIL'})", file=sys.stderr, flush=True))
            emit(report)
            return 0 if report["local_passed_development"] else 1
        provider = Ollama(args.model, args.ollama_port) if getattr(args, "model", None) else Baseline()
        if args.command == "fixture":
            emit(fixture(args.scenario))
            return 0
        if args.command == "eval":
            report = evaluate(provider)
            emit(report)
            return 0 if report["passed"] else 1
        if args.command == "drill-eval":
            from .drills import evaluate_drills
            report = evaluate_drills(args.sim_repo, provider)
            emit(report)
            return 0 if report["passed"] else 1
        store = EvidenceStore(args.store)
        if args.command == "demo":
            emit(Agent(store, provider).assess(fixture(args.scenario)))
        elif args.command == "assess":
            emit(Agent(store, provider).assess(read_json(args.observation), args.task))
        elif args.command == "verify":
            emit(store.verify(read_json(args.anchor) if args.anchor else None))
        elif args.command == "export":
            emit(store.bundle())
        elif args.command == "serve":
            from .server import make_server
            server = make_server(store, args.port, provider)
            print(f"Research workbench: http://127.0.0.1:{server.server_port}\nProvider: {provider.name}\nSynthetic only. Ctrl+C to stop.", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
        return 0
    except (Rejected, EvidenceError, OSError, ValueError, sqlite3.Error) as exc:
        print(f"No advice released: {exc}", file=sys.stderr)
        return 2
    finally:
        if store is not None:
            store.close()
