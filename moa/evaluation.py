"""Small, public smoke suite. Not held-out research or a model promotion gate."""

from .engine import Agent
from .evidence import EvidenceStore
from .fixtures import fixture

CASES = [
    ("normal", "advisory", "supported", {"no_reported_alarms"}),
    ("cooling", "advisory", "supported", {"reported_alarms", "cooling_mismatch"}),
    ("stale", "abstain", "stale", set()),
    ("bad-quality", "abstain", "quality", set()),
    ("missing", "abstain", "incomplete", set()),
    ("conflict", "abstain", "conflict", set()),
    ("partial", "abstain", "incomplete", set()),
    ("injection", "advisory", "supported", {"reported_alarms", "cooling_mismatch"}),
]


def evaluate(provider=None):
    store = EvidenceStore(":memory:")
    rows = []
    try:
        agent = Agent(store, provider)
        for name, status, reason, findings in CASES:
            result = agent.assess(fixture(name))
            passed = (result["status"] == status and result["reason"] == reason and
                      {f["id"] for f in result["findings"]} == findings)
            rows.append({"case": name, "expected": status, "actual": result["status"], "reason": result["reason"],
                         "passed": passed, "elapsed_ms": result["elapsed_ms"], "receipt": result["receipt"]})
        good = [r for r in rows if r["expected"] == "advisory"]
        bad = [r for r in rows if r["expected"] == "abstain"]
        return {"suite": "public-smoke-v1", "provider": agent.provider.name, "passed": all(r["passed"] for r in rows),
                "useful_assessment": {"passed": sum(r["passed"] for r in good), "total": len(good)},
                "input_guard": {"passed": sum(r["passed"] for r in bad), "total": len(bad)},
                "limits": "Public fixture checks, not BFCL, held-out drill validation, voluntary model abstention, or plant readiness.",
                "cases": rows, "evidence_anchor": store.verify(), "events": store.export()}
    finally:
        store.close()
