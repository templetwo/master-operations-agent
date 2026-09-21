# Policy-only holdout campaign

The candidate is the exact policy-only prompt from the v0.6 development experiment. Its canonical JSON-string digest is `31ae7ee05f17f1f2501083e3e826ad615e0e6adf550f35dafddf754f933aa404`. No finding/check rule, release validator, default prompt or default provider is changed for this campaign.

Preparation includes an isolated evaluator runner, public preregistration and secondary metrics fixed before inference. The preserved [holdout protocol](../../docs/holdout-protocol.md) still requires 24/24 useful releases, 6/6 correct guards and no unexpected guard release. Both deterministic and always-refuse controls must meet their expectations before cloud inference. Full private inputs, labels, order, outputs and diagnostic reports remain outside Git. Only aggregate receipts are published here.

[Packaging verification](packaging.json) records a Python 3.10 wheel build, corrected package discovery, consistent 0.7.0 version and a deterministic smoke assessment from the unpacked wheel. This check used no model calls.

The holdout author and reviewer had disclosed implementation exposure. The evaluator-runner author is the previously exposed reviewer; the coordinating/tuning role remains unexposed to private content. A different isolated agent will execute the frozen campaign after preregistration publication. This separation does not establish independent process truth, controls-engineer review or external attestation of provider calls.

Status at preparation: no campaign evaluation started. Subsequent aggregate result receipts must state whether the run completed, control status, fixed-denominator usefulness and guards, all failures, inference-call counts and source integrity. Failure or interruption is published without changing labels or tuning the candidate. No automatic model promotion is authorized by this research gate.

See [implementation provenance](../../docs/provenance.md), [failure accounting](../../docs/failure-schema.md) and the [separate explanation-task proposal](../../docs/next-explanation-task.md).
