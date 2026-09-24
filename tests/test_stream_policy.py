"""Authored dependency examples for the new policy, not model evaluations."""

import copy
import unittest

from moa import stream_policy as policy
from moa.knowledge import POLICY_HASH as LEGACY_HASH


UNITS = dict(zip(policy.TAGS, ("M3/H", "%", "M3/H", "DEG C", "DEG C")))
BASE = {"FI100": 60000, "LIC101": 50000, "FIC102": 60000, "TIC201": 150000, "TIC202": 40000}


def configuration():
    return {"model_id": "0" * 64, "tags": {tag: {
        "unit": UNITS[tag], "lo": 0, "hi": 200 if tag == "TIC201" else 100,
        "alarms": {}, "sp_limits": None, "op_limits": None,
        "kind": "ind" if tag == "FI100" else "pid", "master": None, "slave": None,
    } for tag in policy.TAGS}, "trips": []}


def observation(index=24, **values):
    current = dict(BASE, **values)
    tick = index * 10
    return {"schema": "1.2", "stream_id": "1" * 64, "seq": tick // 2 + 1,
            "tick": tick, "sim_time_ms": tick * 500, "captured_at": None,
            "points": [{"tag": tag, "value_milli": current[tag], "unit": UNITS[tag],
                        "source_quality": "GOOD", "sample_tick": tick, "sample_sim_time_ms": tick * 500,
                        "mode": None if tag == "FI100" else "AUTO", "sp_milli": None if tag == "FI100" else current[tag],
                        "op_milli": None if tag == "FI100" else 70000, "control_revision": 0} for tag in policy.TAGS],
            "alarms": [], "alarms_total_matched": 0, "alarms_omitted": 0}


def point(row, tag):
    return next(p for p in row["points"] if p["tag"] == tag)


def quiet_grid():
    return [observation(i) for i in range(25)]


def bad(row, tag):
    point(row, tag).update(source_quality="BAD", value_milli=None)


def alarm(row, active=True):
    row["alarms"] = [{"episode_id": "alarm.1.1", "target": "TIC201", "condition": "PVHI",
                      "priority": "High", "active": active, "acknowledged": False, "first_observed_sim_ms": 0}]
    row["alarms_total_matched"] = 1


class StreamPolicyTests(unittest.TestCase):
    def assess(self, grid, sample=None, **kwargs):
        return policy.assess(sample or grid[-1], grid, configuration(), **kwargs)

    def test_quiet_full_scope_has_no_unresolved_cause(self):
        result = self.assess(quiet_grid())
        self.assertEqual(result["outcome"], "normal_within_scope")
        self.assertEqual(set(result["findings"]), {"no_reported_alarms", "no_large_net_change"})
        self.assertEqual(set(result["checks"]), {"continue_observation", "compare_independent_measurement"})
        self.assertEqual(result["withheld"], [])

    def test_startup_does_not_invent_trends_but_instants_work(self):
        row = observation(0)
        grid = [None] * 24 + [row]
        result = self.assess(grid)
        self.assertEqual(result["outcome"], "no_finding_supported")
        self.assertNotIn("no_large_net_change", result["findings"])
        self.assertNotIn("cause_unresolved", result["findings"])
        self.assertIn({"finding": "reactor_warming", "reason": "incomplete_history"}, result["withheld"])
        alarm(row)
        point(row, "TIC202")["op_milli"] = 95000
        result = self.assess(grid)
        self.assertEqual(result["outcome"], "advisory")
        self.assertEqual(set(result["findings"]), {"reported_alarms", "coolant_output_high"})

    def test_integer_thresholds_and_actual_change_cause(self):
        cases = [("TIC201", 1999, set()), ("TIC201", 2000, {"reactor_warming"}),
                 ("TIC201", -2000, {"reactor_cooling"}), ("TIC202", 3000, {"jacket_warming"}),
                 ("FIC102", 5000, {"feed_flow_increased"}), ("LIC101", 3000, {"tank_level_increased"})]
        for tag, delta, expected in cases:
            with self.subTest(tag=tag, delta=delta):
                grid = quiet_grid()
                point(grid[-1], tag)["value_milli"] += delta
                result = self.assess(grid)
                self.assertEqual(set(result["findings"]) & set(policy.CHANGE_FINDINGS), expected)
                self.assertEqual("cause_unresolved" in result["findings"], bool(expected))

    def test_interior_peak_can_coexist_with_small_net_change_but_is_not_normal(self):
        grid = quiet_grid()
        point(grid[12], "TIC201")["value_milli"] += 2000
        result = self.assess(grid)
        self.assertTrue({"reactor_below_window_peak", "no_large_net_change", "cause_unresolved"} <= set(result["findings"]))
        self.assertIn("monitor_thermal_recovery", result["checks"])
        self.assertEqual(result["outcome"], "advisory")

    def test_missing_grid_slot_withholds_trends_without_filling_it(self):
        grid = quiet_grid()
        grid[12] = None
        point(grid[-1], "TIC201")["value_milli"] += 4000
        result = self.assess(grid)
        self.assertNotIn("reactor_warming", result["findings"])
        self.assertNotIn("no_large_net_change", result["findings"])
        self.assertIn("capture_clean_window", result["checks"])
        self.assertEqual(result["outcome"], "no_finding_supported")

    def test_latest_bad_feed_invalidates_cached_feed_only(self):
        grid = quiet_grid()
        for tag, delta in (("FIC102", 5000), ("LIC101", 3000), ("TIC201", 2000)):
            point(grid[-1], tag)["value_milli"] += delta
        latest = copy.deepcopy(grid[-1])
        latest.update(seq=latest["seq"] + 1, tick=latest["tick"] + 2, sim_time_ms=latest["sim_time_ms"] + 1000)
        for p in latest["points"]:
            p.update(sample_tick=latest["tick"], sample_sim_time_ms=latest["sim_time_ms"])
        bad(latest, "FIC102")
        result = self.assess(grid, latest)
        self.assertEqual(result["outcome"], "observation_incomplete")
        self.assertTrue({"reactor_warming", "tank_level_increased", "cause_unresolved"} <= set(result["findings"]))
        self.assertNotIn("feed_flow_increased", result["findings"])
        self.assertNotIn("no_large_net_change", result["findings"])
        self.assertIn({"finding": "feed_flow_increased", "reason": "current_measurement_unusable"}, result["withheld"])
        self.assertEqual(result["unusable_measurements"], [{"finding": "unusable_measurement", "tag": "FIC102",
                         "reason": "source_quality_bad", "text": policy.UNUSABLE_TEXT["source_quality_bad"]}])

    def test_bad_feed_history_does_not_erase_reactor_or_level_evidence(self):
        grid = quiet_grid()
        bad(grid[12], "FIC102")
        point(grid[-1], "TIC201")["value_milli"] += 2000
        point(grid[-1], "LIC101")["value_milli"] += 3000
        result = self.assess(grid)
        self.assertTrue({"reactor_warming", "tank_level_increased"} <= set(result["findings"]))
        self.assertIn({"finding": "feed_flow_increased", "reason": "historical_measurement_unusable"}, result["withheld"])
        self.assertEqual(result["unusable_measurements"], [])
        self.assertEqual(result["outcome"], "observation_incomplete")

    def test_bad_jacket_pv_does_not_invalidate_present_output(self):
        grid = quiet_grid()
        point(grid[-1], "TIC201")["value_milli"] += 2000
        point(grid[-1], "TIC202")["op_milli"] = 95000
        bad(grid[-1], "TIC202")
        result = self.assess(grid)
        self.assertTrue({"reactor_warming", "coolant_output_high"} <= set(result["findings"]))
        self.assertNotIn("jacket_warming", result["findings"])
        self.assertNotIn("cooling_path_unconfirmed", result["findings"])

    def test_upstream_meter_failure_does_not_substitute_for_feed_loop_quality(self):
        grid = quiet_grid()
        bad(grid[-1], "FI100")
        point(grid[-1], "FIC102")["value_milli"] += 5000
        result = self.assess(grid)
        self.assertIn("feed_flow_increased", result["findings"])
        self.assertEqual(result["unusable_measurements"][0]["tag"], "FI100")
        self.assertEqual(result["outcome"], "observation_incomplete")
        # No FI100 history rule exists. A recovered past FI100 fault must not
        # poison other tags' reliable history in scoped mode.
        grid = quiet_grid()
        bad(grid[12], "FI100")
        self.assertEqual(self.assess(grid)["outcome"], "normal_within_scope")

    def test_global_flag_withholds_all_findings_including_alarm_ids(self):
        grid = quiet_grid()
        bad(grid[-1], "FIC102")
        point(grid[-1], "TIC201")["value_milli"] += 2000
        point(grid[-1], "TIC202")["op_milli"] = 98000
        alarm(grid[-1])
        result = self.assess(grid, scoped_degradation=False)
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["outcome"], "observation_incomplete")
        self.assertEqual({row["reason"] for row in result["withheld"]}, {"global_quality_gate"})
        self.assertEqual({row["finding"] for row in result["withheld"]}, set(policy.DEPENDENCIES))
        self.assertEqual(result["unusable_measurements"][0]["tag"], "FIC102")

    def test_high_output_alone_is_attention_without_a_causal_change_claim(self):
        grid = quiet_grid()
        point(grid[-1], "TIC202")["op_milli"] = 95000
        result = self.assess(grid)
        self.assertIn("coolant_output_high", result["findings"])
        self.assertNotIn("cause_unresolved", result["findings"])
        self.assertEqual(result["outcome"], "advisory")

    def test_range_flag_preserves_source_quality_and_values(self):
        grid = quiet_grid()
        for row in grid:
            point(row, "TIC202")["value_milli"] = 170600
        frozen = copy.deepcopy(grid)
        result = self.assess(grid)
        self.assertEqual(result["derived"]["TIC202"], {"over_range": True})
        self.assertIn("no_large_net_change", result["findings"])
        self.assertEqual(result["unusable_measurements"], [])
        self.assertNotEqual(result["outcome"], "normal_within_scope")
        self.assertEqual(grid, frozen)
        self.assertEqual(point(grid[-1], "TIC202")["source_quality"], "GOOD")

    def test_incomplete_alarm_coverage_never_asserts_absence(self):
        grid = quiet_grid()
        grid[-1].update(alarms_total_matched=1, alarms_omitted=1)
        result = self.assess(grid)
        self.assertEqual(result["outcome"], "observation_incomplete")
        self.assertNotIn("no_reported_alarms", result["findings"])
        self.assertIn({"finding": "no_reported_alarms", "reason": "incomplete_alarm_coverage"}, result["withheld"])

    def test_recovery_with_active_alarm_cannot_be_normal(self):
        grid = quiet_grid()
        point(grid[-1], "TIC201")["value_milli"] -= 2000
        alarm(grid[-1])
        result = self.assess(grid)
        self.assertIn("reactor_cooling", result["findings"])
        self.assertIn("monitor_thermal_recovery", result["checks"])
        self.assertEqual(result["outcome"], "advisory")
        grid = quiet_grid()
        alarm(grid[-1])
        self.assertEqual(self.assess(grid)["outcome"], "advisory")

    def test_policy_read_is_detached_and_legacy_identity_unchanged(self):
        catalog = policy.read_policy()
        self.assertEqual(catalog["id"], "lab-v2-deps")
        self.assertEqual(catalog["dependencies"]["feed_flow_increased"]["tags"], ["FIC102"])
        catalog["dependencies"]["feed_flow_increased"]["tags"].append("FI100")
        catalog["findings"]["reactor_warming"] = "changed"
        self.assertEqual(policy.read_policy()["dependencies"]["feed_flow_increased"]["tags"], ["FIC102"])
        self.assertNotEqual(policy.read_policy()["findings"]["reactor_warming"], "changed")
        self.assertEqual(LEGACY_HASH, "4a4242bbaa82b5d52e1336451b467d3ac8dff51fcb7999c6f940b5e90cd39ef1")


if __name__ == "__main__":
    unittest.main()
