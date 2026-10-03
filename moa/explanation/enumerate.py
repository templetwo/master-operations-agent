"""Public enumerator of reachable window kernels, so caps are measured, not inferred.

The grid covers every finding the window rules can emit: a 4-sample reactor
series over six levels, jacket, feed and level deltas on both sides of their
thresholds, coolant output on both sides of 95 percent, alarms on or off, and
one unreliable history sample on or off. It reaches 202 distinct outcomes.
"""

import itertools
from datetime import datetime, timezone

from ..contracts import stamp
from ..knowledge import eligible

T0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
UNITS = {"TIC201": "DEG C", "TIC202": "DEG C", "FIC102": "M3/H", "LIC101": "%", "TIC202.OP": "%"}


def window_observation(series, *, alarms=True, unreliable=False, now=T0):
    t = stamp(now)
    samples = []
    for index in range(len(series["TIC201"])):
        quality = {tag: "good" for tag in UNITS}
        if unreliable and index == 1:
            quality["TIC201"] = "bad"
        samples.append({"sequence": index, "elapsed_s": index * 10,
                        "values": {tag: series[tag][index] for tag in UNITS}, "quality": quality})
    return {"schema_version": "1.1", "snapshot_id": "enumerated-window", "captured_at": t, "profile": "ess-u1-window-v1",
            "source": {"kind": "synthetic", "adapter": "ess-window-v1", "revision": "enumerated-v1", "model_id": "enumerated-v1"},
            "tags": [{"id": tag, "value": samples[-1]["values"][tag], "unit": unit, "quality": "good", "observed_at": t}
                     for tag, unit in UNITS.items()],
            "alarms": [{"id": "a1", "tag": "TIC201", "condition": "PVHI", "priority": "High", "state": "UNACK"}] if alarms else [],
            "alarm_coverage": "complete",
            "history": {"clock": "simulation_seconds", "epoch_id": "enumerated", "sequence": len(samples) - 1,
                        "sample_period_s": 10, "samples": samples}}


def reachable_window_outcomes():
    """Map each distinct (finding ids, check ids) pair to one witness."""
    seen = {}
    for reactor in itertools.product((0, 1, 2, 3, 5, 10), repeat=4):
        for jacket, feed, level, output, alarms, unreliable in itertools.product(
                (0, 3, -3), (0, 5), (0, 3), (94, 95), (True, False), (False, True)):
            series = {"TIC201": list(reactor), "TIC202": [10, 10, 10, 10 + jacket], "FIC102": [20, 20, 20, 20 + feed],
                      "LIC101": [30, 30, 30, 30 + level], "TIC202.OP": [50, 50, 50, output]}
            findings, checks, _, _ = eligible(window_observation(series, alarms=alarms, unreliable=unreliable))
            seen.setdefault((tuple(findings), tuple(checks)), {"series": series, "alarms": alarms, "unreliable": unreliable})
    return seen
