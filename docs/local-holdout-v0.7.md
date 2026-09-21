# Registered local comparison extension

The user requested a retest of the previously tested local models after the v0.7 DeepSeek campaign. This is a new comparative extension on the same private u1-v1 corpus. It does not repeat or replace the cloud campaign, alter the private freeze, or describe the corpus as a new unseen benchmark. The coordinator has seen aggregate cloud outcomes but no private observations, labels, case IDs or per-case diagnoses. The evaluator previously executed the cloud campaign and is now corpus-exposed; that role must not tune the candidate.

Candidates are tested in this fixed order:

| Installed model | Required artifact digest |
|---|---|
| `qwen3:4b` | `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7` |
| `qwen3.5:9b-q4_K_M` | `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` |

Use the exact v0.6 policy-only prompt with canonical digest `31ae7ee05f17f1f2501083e3e826ad615e0e6adf550f35dafddf754f933aa404`. Engine, rules, validator, prompt and private labels remain unchanged. The private reviewed manifest remains `29aad4f3c8bfa841954925f378a2a740659246a5a0af31f515b328a85fa845e0`. The original cloud claim, protocol and receipts remain intact.

The provider is the existing numeric-loopback Ollama adapter, port 11434, with reported server version 0.32.6. Requested settings remain temperature 0, seed 0, 8192 context, 768 generated tokens, thinking disabled, nonstreaming output, declared-order union JSON schema and five-minute keep-alive. The socket timeout stays 20 seconds, the observation freshness budget 60 seconds, and the agent limit six response turns. Neither timeout nor context is enlarged after observing a failure. These are requested settings, not attestation that a trusted daemon enforces them. No downloads, cloud fallback, API keys or alternate models are used.

Local structured-schema decoding differs from the cloud JSON-object mode. Comparing scores therefore compares these provider configurations, not model weights in isolation. Model metadata, schema and template hashes, source hashes, protocol hash and server version are frozen or checked. The hardware and initial loaded-model inventory are recorded separately. Models run sequentially. No model is unloaded to manufacture a cold timing result, and this run does not establish exclusive use of the machine or daemon.

Publish registration before private execution. One persistent local campaign claim prevents replacement of the first attempt. Each model receives one unscored protocol warmup without a private observation, then exactly one assessment per frozen case in frozen order. A failed warmup ends that model's arm before scored cases, with an incomplete result rather than a usefulness estimate. Maximum 145 completion attempts per model, 290 across both, including warmups. The six input guards should require zero model calls. There are no inference retries, wrapper repairs, label changes, best-run selection or prompt changes.

Run the baseline and always-refuse controls before candidate inference. Baseline must match all 24 usable expectations and six guards; refusal must achieve zero useful answers and six guards. A mismatch stops the comparison without repairing labels. The primary gate for each candidate remains 24/24 exact useful releases, 6/6 correct guards and zero unexpected guard advisories. Guard success is attributed to input validation, not learned model abstention.

Keep the existing secondary metrics: complete reads, unmodified advice-envelope validity, exact finding/check/evidence sets, identifier precision/recall and omissions/extras, unsupported released IDs, and exact evidence fidelity. Undefined zero denominators remain null. Each primary denominator stays 24 usable and six guards even if execution stops early. Diagnostic ID totals on an interrupted arm cover observed attempts only. Whole-assessment latency separates useful accepted, withheld usable, all usable and guard cohorts; it is not time to first token. There is no newly chosen latency or severity threshold.

Materialize a fresh observation immediately before each assessment and keep the real clock moving. Never renew an old observation to rescue stale output. Delivered malformed or truncated content from the pinned local provider counts as a failed usable attempt. A transport, model identity or setup failure stops that candidate with an incomplete status and retained attempts. The second registered model may proceed after shared source/freeze checks and its own server-version/artifact preflight; this is not a retry of the failed candidate. A shared integrity or control failure prevents further inference.

All inputs, expectations, case order, detailed outcomes, protocol transcripts and hash-linked evidence stay in a new private campaign directory outside the repository and frozen corpus. Public receipts contain allowlisted aggregate fields only. The evaluator verifies private chains, result bindings and completion accounting after execution without more inference. Root receives only public aggregates, methodology and hashes. Persistent claims and local hashes do not prevent a privileged actor from replacing a whole history and do not externally attest inference.

Tests use public toy fixtures only. This protocol is a policy-compliance retest, not independent process truth, cross-unit generalization, an LLM added-value demonstration, or plant authorization. Publish failure and interruption as well as success. Do not promote either model automatically.

Registration requires no access to the private corpus:

```sh
python3 -m moa.local_holdout register --output receipts/v0.7-local/preregistration.json
```

After public publication, the isolated evaluator runs the following once, with new output paths and the exact published registration hash:

```sh
python3 -m moa.local_holdout run \
  --package /PRIVATE/holdouts/u1-v1 \
  --private-output /PRIVATE/campaigns/u1-v1-local-v07 \
  --public-output receipts/v0.7-local/aggregate.json \
  --preregistration receipts/v0.7-local/preregistration.json \
  --expected-sha256 REGISTERED_FILE_SHA256
```
