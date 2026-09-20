"""Release failures are classified by the boundary reached, not reason alone."""

import copy
import unittest
from datetime import timedelta

from moa.contracts import Rejected, now_utc
from moa.drills import summarize_rows
from moa.engine import Agent, SYSTEM
from moa.evidence import EvidenceStore
from moa.fixtures import fixture
from moa.providers import Baseline


class Scripted:
    name = "accounting-test-double"

    def __init__(self, *responses):
        self.responses = iter(responses)

    def respond(self, messages):
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)


READS = [{"kind": "tool", "name": name, "arguments": {}} for name in ("read_snapshot", "read_policy")]
ADVICE = {"kind": "advice", "finding_ids": ["reported_alarms", "cooling_mismatch"],
          "check_ids": ["review_cooling_evidence", "compare_independent_measurement", "inspect_alarm_context"],
          "evidence": ["snapshot:alarms", "policy:lab-v2", "tag:TT101", "tag:FT102"]}


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.store = EvidenceStore(":memory:")
        self.addCleanup(self.store.close)

    def assess(self, provider=None, observation=None, **kwargs):
        return Agent(self.store, provider, **kwargs).assess(fixture() if observation is None else observation)

    def assert_failure(self, result, code, stage, category):
        self.assertEqual(result["status"], "abstain")
        self.assertEqual(result["reason"], code)
        self.assertEqual(result["failure"], {"code": code, "stage": stage, "category": category})
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["checks"], [])

    def test_same_generic_schema_code_keeps_input_tool_and_candidate_separate(self):
        extra = {"unexpected": True}
        invalid_input = self.assess(observation=dict(fixture(), **extra))
        bad_tool_envelope = self.assess(Scripted(dict(READS[0], **extra)))
        bad_tool_arguments = self.assess(Scripted(dict(READS[0], arguments=extra)))
        bad_candidate = self.assess(Scripted(*READS, dict(ADVICE, **extra)))
        self.assert_failure(invalid_input, "schema", "input_validation", "input_validation")
        self.assert_failure(bad_tool_envelope, "schema", "tool_request", "tool_protocol")
        self.assert_failure(bad_tool_arguments, "schema", "tool_execution", "tool_protocol")
        self.assert_failure(bad_candidate, "schema", "candidate_validation", "candidate_shape")
        outcomes = [e["payload"]["data"] for e in self.store.export() if e["payload"]["kind"] == "outcome"]
        self.assertEqual([r["failure"] for r in outcomes], [r["failure"] for r in
                         (invalid_input, bad_tool_envelope, bad_tool_arguments, bad_candidate)])

    def test_provider_preparation_response_and_json_parsing_are_not_candidate_failures(self):
        class BadPreparation(Scripted):
            def prepare(self):
                raise Rejected("schema", "Malformed provider listing.")
        self.assert_failure(self.assess(BadPreparation()), "schema", "provider_prepare", "provider_preparation")
        for code in ("schema", "invalid_json", "provider_http_error"):
            with self.subTest(code=code):
                result = self.assess(Scripted(Rejected(code, "Provider adapter could not return a response.")))
                self.assert_failure(result, code, "provider_response", "provider_response")

    def test_candidate_shape_content_abstention_and_budget_are_distinct(self):
        self.assert_failure(self.assess(Scripted({"wrapped": ADVICE})), "candidate_schema", "response_envelope", "candidate_shape")
        self.assert_failure(self.assess(Scripted(*READS, dict(ADVICE, check_ids=[]))),
                            "candidate_schema", "candidate_validation", "candidate_shape")
        self.assert_failure(self.assess(Scripted(*READS, dict(ADVICE, check_ids=["open_valve"]))),
                            "unsupported_check", "candidate_validation", "candidate_content")
        self.assert_failure(self.assess(Scripted(ADVICE)), "ungrounded", "candidate_validation", "candidate_content")
        self.assert_failure(self.assess(Scripted({"kind": "abstain", "reason": "insufficient_evidence"})),
                            "model_abstained", "abstention", "model_abstention")
        self.assert_failure(self.assess(Scripted(*([READS[0]] * 6))), "tool_budget", "reasoning_budget", "budget")
        self.assert_failure(self.assess(Scripted(Rejected("provider_budget", "Call budget exhausted."))),
                            "provider_budget", "provider_response", "budget")

    def test_expiration_after_generation_is_not_initial_input_failure(self):
        current = now_utc()
        clock = [current]
        class SlowBaseline(Baseline):
            def respond(self, messages):
                reply = super().respond(messages)
                if reply["kind"] == "advice":
                    clock[0] += timedelta(seconds=61)
                return reply
        self.assert_failure(self.assess(SlowBaseline(), fixture(now=current), clock=lambda: clock[0]),
                            "stale", "freshness_validation", "input_freshness")

    def test_summary_reconciles_all_withheld_runs_and_fixed_cohorts(self):
        results = [self.assess(),
                   self.assess(Scripted(*READS, dict(ADVICE, unexpected=True))),
                   self.assess(Scripted(*READS, dict(ADVICE, check_ids=["open_valve"]))),
                   self.assess(Scripted(dict(READS[0], arguments={"unexpected": True}))),
                   self.assess(Scripted({"kind": "abstain", "reason": "insufficient_evidence"})),
                   self.assess(Scripted(Rejected("provider_error", "Unavailable."))),
                   self.assess(observation=dict(fixture(), unexpected=True)),
                   self.assess(observation=fixture("stale"))]
        rows = [{"expected": {"status": "advisory" if i < 6 else "abstain"}, "actual": result,
                 "passed": i in {0, 6, 7}, "evidence_fidelity": True if i == 0 else None}
                for i, result in enumerate(results)]
        metrics = summarize_rows(rows)
        self.assertEqual(metrics["candidate_rejections"], 2)
        self.assertEqual(metrics["useful_assessment"], {"passed": 1, "total": 6})
        self.assertEqual(metrics["input_guards"], {"passed": 2, "total": 2})
        accounting = metrics["failure_accounting"]
        self.assertEqual((accounting["total"], accounting["released"], accounting["withheld"]), (8, 1, 7))
        self.assertEqual(accounting["by_category"], {"candidate_shape": 1, "candidate_content": 1,
                         "tool_protocol": 1, "model_abstention": 1, "provider_response": 1, "input_validation": 2})
        for field in ("by_category", "by_stage", "by_reason"):
            self.assertEqual(sum(accounting[field].values()), accounting["withheld"])
        self.assertEqual(accounting["usable_observations"]["failed"], 5)
        self.assertEqual(accounting["usable_observations"]["withheld"], 5)
        self.assertEqual(accounting["guard_observations"]["failed"], 0)
        self.assertEqual(accounting["guard_observations"]["withheld"], 2)
        self.assertEqual(accounting["by_reason"]["schema"], 3)

    def test_historical_missing_stage_is_unclassified_and_empty_summary_is_explicit(self):
        row = {"expected": {"status": "advisory"}, "actual": {"status": "abstain", "reason": "schema", "elapsed_ms": 1},
               "passed": False, "evidence_fidelity": None}
        metrics = summarize_rows([row])
        self.assertEqual(metrics["failure_accounting"]["by_category"], {"unclassified": 1})
        self.assertEqual(metrics["candidate_rejections"], 0)
        self.assertEqual(summarize_rows([])["end_to_end_ms"], {"count": 0, "median": None, "max": None})

    def test_experiment_prompt_is_recorded_and_used_without_changing_default(self):
        seen = []
        class Recording(Baseline):
            def respond(self, messages):
                seen.append(messages[0]["content"])
                return super().respond(messages)
        prompt = SYSTEM + "\nTrusted experiment addendum."
        agent = Agent(self.store, Recording(), system_prompt=prompt)
        with self.assertRaises(AttributeError):
            agent.system_prompt = "mutated"
        result = agent.assess(fixture())
        self.assertEqual(result["status"], "advisory")
        self.assertNotIn("failure", result)
        self.assertEqual(seen, [prompt] * 3)
        first = self.store.export()[0]["payload"]["data"]
        self.assertEqual(first["system_prompt"], prompt)
        self.assertEqual(Agent(self.store).system_prompt, SYSTEM)


if __name__ == "__main__":
    unittest.main()
