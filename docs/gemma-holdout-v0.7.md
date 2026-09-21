# Registered Gemma GGUF comparison extension

This is one new candidate configuration on the existing private u1-v1 corpus, after the DeepSeek and Qwen campaigns. It is not a new unseen dataset. The coordinator has seen aggregate prior results and public probe transcripts, but no private observations, labels, case IDs or per-case diagnoses. The executing evaluator has prior corpus exposure and may execute and audit, but must not tune the candidate.

The single candidate is `gemma4:12b-it-q4_K_M`, digest `4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c`, using Ollama 0.32.6. It was downloaded from the official Ollama library with user authorization. The earlier MLX build failed a public schema probe. This GGUF build passed that probe and completed one public operations window with four calls, whose candidate failed content validation. That development result is preserved; it caused no prompt, validator, policy, budget or label change. The model is not promoted by compatibility success.

Use the original policy-only prompt with canonical digest `31ae7ee05f17f1f2501083e3e826ad615e0e6adf550f35dafddf754f933aa404`. Engine, rules, validator and private labels remain unchanged. The reviewed manifest stays `29aad4f3c8bfa841954925f378a2a740659246a5a0af31f515b328a85fa845e0`. Preserve all prior campaign claims and receipts. A new persistent claim for this corpus, prompt and model configuration must prevent replacing the first Gemma attempt.

Use the existing numeric-loopback Ollama adapter at port 11434: temperature 0, seed 0, 8,192 context tokens, 768 generated tokens, thinking disabled, nonstreaming output, declared-order union JSON schema, five-minute keep-alive and 20-second socket timeout. Keep the moving 60-second observation freshness budget and six-turn agent limit. Do not enlarge limits after a failure. Requested settings and daemon metadata are not independent proof of enforcement. Temperature 0 is the comparison setting, while the model's installed default temperature is 1; this is not a vendor-default performance claim.

Freeze source hashes, protocol and inventory hashes, model identity, template and parameter hashes, prompt and response-schema hashes. Publish the registration before any private execution. The same machine and sequential testing permit cache, load and order effects. GGUF and MLX differ in representation and quantization as well as backend; this campaign cannot isolate backend causality. Cloud structured JSON mode also differs from local constrained decoding. Compare the tested configurations, not model weights alone.

Run deterministic baseline and always-refuse controls before any candidate request. Baseline must match all 24 usable expectations and six guards. Refusal must achieve zero useful answers and all six guards. Stop on disagreement without label repair. Then make one public protocol warmup without private observations and one assessment per frozen case in frozen order. A failed warmup stops the study before scored cases and yields an incomplete result. Maximum 145 completion attempts including warmup. Expected guard inference is zero. Public compatibility probes are separate from these 145 calls and are not scored.

The primary gate remains 24/24 exact useful releases, 6/6 correct guards and zero unexpected guard advisories. Guard success belongs to input validation, not learned abstention. Preserve required-read completion, original envelope validity, exact finding/check/evidence sets, identifier precision/recall and extras/omissions, unsupported released IDs and evidence fidelity as separate diagnostics. Undefined denominators remain null. Primary denominators remain 24 usable and six guards if interrupted; observed-only ID totals must be labeled accordingly. Latencies are whole assessments with accepted, withheld, all-usable and guard cohorts, not time to first token. No new severity or latency threshold is selected.

Materialize fresh observations immediately before each assessment, with the real clock moving. Do not renew stale observations to rescue a result. Delivered malformed or truncated model content is a failed attempt. Transport, identity, setup, shared-integrity or control failures stop the single candidate and retain an incomplete outcome. No alternate model, retry, output repair, best-run selection, prompt tuning, label change, cloud fallback or further download is allowed within this campaign.

Store inputs, expectations, case order, detailed outcomes, provider transcripts and hash-linked evidence in a new private directory outside the repository and frozen corpus. Publish only allowlisted aggregates. The evaluator verifies chains, artifact hashes, result bindings, request/completion accounting and prior-claim preservation without more inference, returning only methodology and aggregates to the coordinator. This is procedural role separation within the same agent team, not an externally independent audit. Local receipts and claims are not external attestation and cannot prevent whole-history replacement by a privileged actor.

Runner tests use public toy fixtures only. Corpus authors' previously disclosed implementation exposure still applies. This study tests a small synthetic policy and contract, not independent process truth, cross-unit generalization, LLM added value or plant authorization. Publish failure or interruption. No automatic model promotion is authorized.

Registration requires no private-corpus access:

```sh
python3 -m moa.gemma_holdout register --output receipts/v0.7-gemma-gguf/preregistration.json
```

After publishing the exact registration, the isolated evaluator executes once:

```sh
python3 -m moa.gemma_holdout run \
  --package /PRIVATE/holdouts/u1-v1 \
  --private-output /PRIVATE/campaigns/u1-v1-gemma-gguf-v07 \
  --public-output receipts/v0.7-gemma-gguf/aggregate.json \
  --preregistration receipts/v0.7-gemma-gguf/preregistration.json \
  --expected-sha256 REGISTERED_FILE_SHA256
```
