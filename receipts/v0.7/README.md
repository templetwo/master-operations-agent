# Policy-only holdout campaign

The candidate is the exact policy-only prompt from the v0.6 development experiment. Its canonical JSON-string digest is `31ae7ee05f17f1f2501083e3e826ad615e0e6adf550f35dafddf754f933aa404`. No finding/check rule, release validator, default prompt or default provider is changed for this campaign.

The isolated campaign completed on 2026-09-21 UTC and **failed the frozen acceptance gate**. [Aggregate result](holdout-aggregate.json). The preserved [holdout protocol](../../docs/holdout-protocol.md) requires 24/24 useful releases, 6/6 correct guards and no unexpected guard release. Both controls passed before cloud inference. Full private inputs, labels, order, outputs and diagnostic reports remain outside Git. Only aggregate receipts are published here.

| Configuration | Useful answers | Correct input guards | Required reads | Valid advice envelopes |
|---|---:|---:|---:|---:|
| Deterministic baseline | 24/24 | 6/6 | 24/24 | 24/24 |
| Always refuse | 0/24 | 6/6 | 0/24 | 0/24 |
| Frozen policy-only DeepSeek | 7/24 | 6/6 | 24/24 | 24/24 |

The 17 withheld usable answers failed candidate-content validation. Exact finding sets matched on 9/24 cases and exact check sets on 12/24; evidence-reference sets matched on 24/24. Across original candidates, findings contained 26 extra IDs and omitted 13 expected IDs; checks contained eight extras and six omissions. This is agreement with authored policy labels, not an independently established process-truth or safety score. No unsupported identifier reached the released output according to those labels, and the seven releases retained exact evidence values.

The cloud run used 96 scored completions and one warmup, within the 145-call cap. Median accepted-answer wall time was 4.431 seconds across seven answers; median wall time across all 24 usable attempts was 4.504 seconds. These are whole-assessment latencies, not time to first token. The result does not establish cloud superiority, model incapacity, or a measured benefit over deterministic calculation.

[Preregistration](holdout-preregistration.json) was published at [commit 96eba34](https://github.com/templetwo/master-operations-agent/commit/96eba349f2dd258de3930615a1bf91e2fcb1d02d). [Anonymous publication verification](preregistration-publication.json) occurred at 02:03:22.310Z, before the campaign began at 02:05:28.475Z; it ended at 02:07:18.908Z. The runner reports source and private freeze unchanged. Primary and secondary gates are both false. No retry, label repair, alternative candidate or model promotion followed this result.

[Packaging verification](packaging.json) records a Python 3.10 wheel build, corrected package discovery, consistent 0.7.0 version and a deterministic smoke assessment from the unpacked wheel. This check used no model calls.

The [full local validation](validation-pre-campaign/validation.json) passed all 113 tests with the trusted simulator enabled, plus deterministic smoke/drills and JavaScript syntax checks. [CI](ci-preregistration.json) passed on Python 3.10, 3.12 and 3.14; CI omits the six optional simulator checks. Passing these tests validates implementation behavior, not model usefulness.

The [isolated evaluator audit](evaluator-audit.json) verified 193 private artifact hashes, all three evidence chains, 90 input/expectation/outcome bindings across the controls and candidate, and all 97 completion-content and request-hash bindings. It independently reproduced the primary result. [Public aggregate reconciliation](aggregate-reconciliation.json) checks the fixed denominators and identifier totals without accessing private cases. Full HTTP response envelopes were not retained, so their stored digests cannot be independently recomputed; the exact completion text and outgoing request hashes were checked. Neither audit externally attests that provider traffic occurred.

The holdout author and reviewer had disclosed implementation exposure. The evaluator-runner author is the previously exposed reviewer; a fresh isolated Codex agent executed the frozen campaign. The coordinating/tuning role received aggregate results, not private observations, labels, IDs or case-level diagnoses. The corpus is now evaluated and cannot be described as an unused benchmark. This separation does not establish independent process truth, controls-engineer review or external attestation of provider calls.

The engineering conclusion is narrow: retain deterministic finding/check selection at this layer. The separate cited-explanation proposal asks whether an LLM adds value after those calculations. That task needs its own rubric and new holdout; it is not implemented or scored here.

See [implementation provenance](../../docs/provenance.md), [failure accounting](../../docs/failure-schema.md) and the [separate explanation-task proposal](../../docs/next-explanation-task.md).
