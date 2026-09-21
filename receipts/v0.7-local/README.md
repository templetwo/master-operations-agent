# Local model retest

New registered comparison of the two previously tested local models, using the unchanged policy-only prompt and private u1-v1 cases. See the [protocol](../../docs/local-holdout-v0.7.md) and [metadata-only inventory](inventory.json). No inference was used to collect the inventory.

The earlier [DeepSeek result](../v0.7/README.md) remains 7/24 useful answers with 6/6 guards. This local extension uses the same case corpus with disclosed prior aggregate feedback and evaluator exposure. Local schema-constrained decoding differs from cloud JSON-object decoding. It is not a new unseen benchmark or a comparison of model weights alone.

Both local arms completed on 2026-09-21 UTC and **failed the acceptance gate**. [Full aggregate](aggregate.json). No retries, exclusions, prompt changes or model promotion occurred.

| Configuration | Useful answers | Input guards | Required reads | Valid advice envelopes | Median usable-attempt wall time |
|---|---:|---:|---:|---:|---:|
| Qwen3 4B, local | 0/24 | 6/6 | 24/24 | 21/24 | 11.875 s |
| Qwen3.5 9B Q4_K_M, local | 0/24 | 6/6 | 24/24 | 24/24 | 16.802 s |
| DeepSeek, earlier cloud campaign | 7/24 | 6/6 | 24/24 | 24/24 | 4.504 s |
| Deterministic baseline, local controls | 24/24 | 6/6 | 24/24 | 24/24 | Not compared |

The always-refuse control scored 0/24 useful and 6/6 guards. All six guards were enforced before inference; those results do not measure learned model abstention. Both local models made 96 scored completions and one warmup each, 194 total, within their registered 145-call caps. There were no transport interruptions. Both kept the registered digest, metadata, server version, source, prompt and private freeze. No useful local answer was released, so useful-answer latency and released-evidence fidelity are undefined. The displayed local latencies describe withheld attempts, not usable service performance or time to first token.

The 4B model had three candidate-shape failures and 21 candidate-content failures. None of its finding or check sets exactly matched the authored expectations; 17/24 evidence-reference sets matched. Across its original candidates, findings contained 67 extras and 47 omissions, checks 45 extras and 30 omissions, and evidence references four extras and 41 omissions.

The 9B model had 24 candidate-content failures despite valid envelopes and completed reads. Only 1/24 finding sets, 3/24 check sets and 2/24 evidence-reference sets matched exactly. Findings contained three extras and 79 omissions, checks four extras and 37 omissions, and evidence references three extras and 105 omissions. Its higher identifier precision does not offset the missing required content. Read completion proves delivery, not comprehension. These comparisons measure agreement with authored policy labels, not independent process truth.

[Registration](preregistration.json) was published at [eaea94e](https://github.com/templetwo/master-operations-agent/commit/eaea94efe2d7dae5263680396a820f1abff282aa). [Anonymous publication verification](preregistration-publication.json) at 03:07:35.465Z preceded the single invocation at 03:10:50.552Z. It finished at 03:22:42.450Z. The 4B arm ran first, then 9B on the same Apple M3 Pro with 18 GiB memory. Fixed order, shared-machine load and different decoding protocols limit causal comparisons with the earlier cloud result.

The [isolated evaluator audit](evaluator-audit.json) verified 262 private artifact hashes, four evidence chains, 120 input/label/outcome bindings and 194 request/completion bindings. It also verified preservation of the prior cloud claim and all 193 retained cloud artifacts. The evaluator was exposed to these cases during the earlier cloud audit and did not tune either candidate. Full HTTP envelopes are not retained, so their digests cannot be recomputed; exact completion content and outgoing requests were audited. Local receipts lack global call sequence numbers, so accounting uses evidence order and retained warmups. Local hashes do not externally attest inference or resist whole-history replacement.

[Full validation](validation/validation.json) passed 122 tests with the trusted simulator, plus deterministic smoke/drills and JavaScript syntax checks. [CI](ci-preregistration.json) passed on Python 3.10, 3.12 and 3.14. [Historical context](historical-context.json) verifies unchanged model artifacts/templates/settings versus the earlier 0/10 development runs. Both case set and policy presentation changed since those runs, so this does not isolate a guidance effect.

The tested local configurations do not qualify to replace deterministic selection. This result does not establish that other local models, prompting methods or tasks would fail. The original cloud result, private corpus and prior receipts remain intact, and no model was promoted.
