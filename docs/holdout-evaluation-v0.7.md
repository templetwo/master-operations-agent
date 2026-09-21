# One sealed policy-only campaign

This protocol evaluates the unchanged v0.6 `policy-only` candidate once on the
previously reviewed private synthetic corpus. It does not authorize plant use,
change the release validator, or claim added value over the deterministic policy.
The prompt digest is `31ae7ee05f17f1f2501083e3e826ad615e0e6adf550f35dafddf754f933aa404`.
The reviewed package manifest digest is
`29aad4f3c8bfa841954925f378a2a740659246a5a0af31f515b328a85fa845e0`.

The runner author reviewed the private corpus during its separate-agent review.
That author has not tuned the candidate from the corpus. A fresh evaluator should
execute this published runner after public preregistration is committed and
published. This is procedural separation within one team, not a blinded controls
engineer or independent organization. The root/tuning role remains unexposed to
observations, expected sets, case identifiers and per-case diagnoses.

`python3 -m moa.holdout register --output receipts/v0.7/holdout-preregistration.json`
creates an immutable public registration. It includes the design, all runtime/test
source hashes, this protocol's hash, provider settings, exact prompt/entry/policy
hashes, and the retained private freeze hash. Registration never opens the corpus
or credentials and makes no model call. Commit and publish the registration before
execution. The full public source revision at registration should also be recorded
in the campaign's publication receipt; source hashes allow a later receipt-only
publication commit without altering the evaluated implementation.

The isolated evaluator invokes:

```sh
python3 -m moa.holdout run \
  --package /PRIVATE/holdouts/u1-v1 \
  --env-file /PRIVATE/project/.env \
  --private-output /PRIVATE/campaigns/u1-v1-policy-only \
  --public-output receipts/v0.7/holdout-aggregate.json \
  --preregistration receipts/v0.7/holdout-preregistration.json \
  --expected-sha256 REGISTERED_FILE_SHA256 \
  --allow-cloud-synthetic
```

Paths are operator-selected. The package and raw campaign outputs must be outside
the repository, with output separate from the frozen package. The evaluator
verifies the reviewed manifest and every covered file before reading cases or
executing the pinned materializer. Symlinks, path escapes and extra package files
are rejected. A persistent exclusive claim beside the package binds this frozen
corpus/prompt pair to one campaign, before any assessment. Failures retain the
claim. No resume or rerun is allowed by this runner. A new study after an
interruption needs explicit review and a different preregistered protocol.

Controls run first in frozen private order. The deterministic baseline must match
all 24 independently authored usable expectations and all six guard expectations.
The always-refuse control must yield zero useful results and six correct guards.
Disagreement stops the campaign before credentials are read or cloud inference
begins. Labels are never repaired to fit the baseline.

Each candidate case has one assessment, bounded by the unchanged six-response
budget. The materializer produces fresh observation wall times and opaque IDs
immediately before assessment, while preserving frozen simulation values. Agent
freshness uses the moving real UTC clock; responses that become stale are withheld
and failed. Intentional time guards are materialized relative to the same current
UTC source, then immediately evaluated. No clock is frozen across model calls,
and no old observation is renewed to rescue an answer.

DeepSeek uses exactly the prior non-thinking JSON-object settings, a 768-token
response cap and temperature zero. One public protocol warmup contains no private
observation. The whole candidate campaign has a maximum of 145 completion calls:
24 usable cases times six responses, plus one warmup. Invalid guard inputs should
be rejected before reaching the provider. The cloud alias is mutable and does
not provide an immutable weight or service-deployment pin.

The primary acceptance threshold remains 24/24 exact released useful assessments,
6/6 correct guards, and zero guard advisories. Secondary checks retain exact
finding/check/evidence sets, 24 complete required-read sequences, zero unsupported
released identifiers, and evidence fidelity of 1.0. With zero releases, fidelity
is undefined and cannot pass. Public reporting separates these conditions rather
than calling guard success useful task completion.

Secondary diagnostics count the original final candidate's identifier matches,
omissions and extras, with micro precision and recall. Missing or malformed lists
contribute no predictions and all expected omissions; precision is null when
nothing was predicted. The fixed primary denominator never shrinks after provider
errors or abstentions. In an interrupted campaign, identifier diagnostic totals
cover observed attempts only and explicitly retain the fixed campaign denominator;
they do not impute omissions for cases that were never attempted. No wrapper
repair, severity weight, retry or alternative
answer is used. Format success means the exact unmodified final advice envelope.
Read completion records delivered evidence, not proof of comprehension. Latency
reports separately cover all usable attempts, useful accepted answers, withheld
usable attempts and guards. No latency threshold or token-cost estimate is used.

Transport, authentication, model-identity, source/freeze integrity or missing
evidence failures stop with an incomplete campaign. Delivered malformed or
truncated output from the confirmed alias remains a failed first attempt and
does not stop the remaining cases. Interruption never yields a passing primary
result. Original attempts, exact inputs, order, responses, hash-linked evidence
and errors remain in new private files. Public output contains only allowlisted
aggregate metrics and integrity hashes. It never publishes case identifiers,
labels, observations, per-case results or arbitrary provider text. The start time
is written privately before controls, then included in the public aggregate.
Controls, source integrity and freeze integrity have separate public fields;
final integrity fields remain null when interruption prevents those checks.

The private output uses exclusive file creation and a final artifact manifest.
The evidence database is append-only through its application API while the run
is active. Neither file permissions nor retained local hashes prevent a
privileged user from replacing whole histories. The final manifest hash is the
public retained comparison anchor, not external attestation.

Tests use public authored fixtures and toy freeze manifests only. Writing and
testing the runner is not a holdout evaluation. Any tuning-role exposure to
private cases or case-level diagnostics retires an unexposed-holdout claim for
that role. Aggregate failure is not grounds for selective retries, label changes
or prompt edits within this registered campaign.
