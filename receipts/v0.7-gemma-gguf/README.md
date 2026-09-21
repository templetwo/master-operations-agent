# Gemma GGUF comparison: incomplete at warmup

The registered run stopped during its single warmup request, before any scored Gemma case. **No holdout accuracy estimate is available.** The fixed-denominator aggregate retains zero observed cases; it must not be presented as a measured 0/24 accuracy score.

| Measurement | Result |
|---|---|
| Candidate | `gemma4:12b-it-q4_K_M`, pinned GGUF Q4_K_M artifact |
| Run status | Incomplete, interrupted during warmup |
| Model completion attempts | 1, entirely warmup |
| Scored model cases | 0 of 30 observed |
| Candidate usefulness, guards and latency | Unmeasured |
| Baseline control | 24/24 useful, 6/6 guards |
| Always-refuse control | 0/24 useful, 6/6 guards |
| Shared source and freeze integrity | Passed |
| Model promotion | Not authorized |

The run lasted from 2026-09-21T10:27:35.675Z to 10:27:57.320Z. The warmup receipt records a generic `provider_error` after 20,006.02 ms, with no response digest or content. Its declared request timeout was 20 seconds. This is consistent with a timeout but does not identify a cold-load, prompt-processing, decoding or other transport cause. Candidate post-run metadata flags remain null because the candidate did not reach final checks; the shared source/freeze check still passed. No retries, repaired output, enlarged budgets, alternate model or replacement attempt occurred.

## Registration and evidence

- [Protocol](../../docs/gemma-holdout-v0.7.md) and [inventory](inventory.json).
- [Preregistration](preregistration.json), SHA-256 `48153b2532ea5dd3dded8e12170e6bd98defbb1a5b676621745f02c01b4650b5`, published in [commit cb7b729](https://github.com/templetwo/master-operations-agent/commit/cb7b729f9ab25e748799256b10709ac84b588ae5) before inference.
- [Publication check](publication-check.json): anonymous byte equality at 09:10:50.019Z, 127 local tests including the trusted simulator, and successful CI on Python 3.10, 3.12 and 3.14.
- [Aggregate](aggregate.json), retaining fixed denominators, zero observed candidate cases and undefined candidate latency/precision metrics.
- [Evaluator audit](evaluator-audit.json): 133 retained artifacts, both control evidence chains and SQLite exports, 60 control result bindings, warmup request hashes and call accounting verified. Prior cloud and Qwen claims/artifacts were preserved. No private observation reached the model, and audit added no inference.

The first evaluator-agent execution request stayed at the escalation step and never created a process, campaign claim or output. After read-only confirmation, the coordinator launched the exact registered subprocess through root UI approval. Its stdout contained only aggregate results; the evaluator agent retained responsibility for private evidence review. This orchestration change did not change the candidate, protocol or scoring. Source, protocol and inventory remained byte-identical to registration.

## Compatibility is a separate result

The earlier [public GGUF probe](../v0.7-gemma/gguf-probe/run.json) passed schema enforcement and completed a public operations window in four calls. That window's candidate failed content validation. Those five diagnostic calls preceded registration and are separate from the campaign's one warmup attempt. They do not provide holdout accuracy or show why the later warmup failed.

The same private synthetic corpus was previously used for DeepSeek and Qwen. This is not a new unseen benchmark, independent process truth, cross-unit generalization or plant authorization. The policy, validator and labels stayed fixed. Local hashes and same-team agent review do not externally attest inference.

The next useful diagnostic is public cold-load versus already-loaded timing for the full protocol warmup. Any changed warmup allowance would require a separately registered configuration and must retain this failed attempt. There is no evidence here supporting a scored-case timeout change or a model-capability conclusion.
