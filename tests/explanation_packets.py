"""Public toy packets for explanation-task tests. No private case content."""
import copy
from datetime import datetime, timezone

from moa import fixtures
from moa.contracts import stamp
from moa.engine import Agent
from moa.evidence import EvidenceStore
from moa.explanation.contract import kernel_of
from moa.providers import Baseline

T0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def kernel_for(observation, when=T0):
    store = EvidenceStore(":memory:")
    try:
        return kernel_of(Agent(store, Baseline(), clock=lambda: when).assess(copy.deepcopy(observation)))
    finally:
        store.close()


def ess_snapshot(alarms=True, now=T0):
    t = stamp(now)
    return {"schema_version": "1.0", "snapshot_id": "authored-snapshot", "captured_at": t, "profile": "ess-u1-v1",
            "source": {"kind": "synthetic", "adapter": "ess-v1", "revision": "authored-v1", "model_id": "authored-v1"},
            "tags": [{"id": "TIC201", "value": 150, "unit": "DEG C", "quality": "good", "observed_at": t},
                     {"id": "TIC202", "value": 40, "unit": "DEG C", "quality": "good", "observed_at": t},
                     {"id": "FIC102", "value": 60, "unit": "M3/H", "quality": "good", "observed_at": t}],
            "alarms": [{"id": "reactor-hi", "tag": "TIC201", "condition": "PVHI", "priority": "High", "state": "UNACK"}] if alarms else [],
            "alarm_coverage": "complete"}


def quality_abstain_observation():
    observation = fixtures.fixture("trend-cooling", now=T0)
    observation["tags"][1]["quality"] = "bad"
    return observation


def packet(name="trend-cooling", *, task_id="t-0001", label="explanation_required", excerpts=None, observation=None, kernel=None):
    observation = fixtures.fixture(name, now=T0) if observation is None else observation
    return {"task_id": task_id, "observation": observation, "kernel": kernel_for(observation) if kernel is None else kernel,
            "excerpts": [] if excerpts is None else excerpts, "label": label}
