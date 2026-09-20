# V0.3: actual local inference and reproducible comparisons

Recorded 2026-09-20. Hardware query: Apple M3 Pro, 19,327,352,832 bytes of unified memory (18 GiB). The local API reported version `0.32.6`. Exact hardware, artifact metadata, requested settings, and source hashes are in each run's `run.json`.

**Result: neither local model produced a useful assessment in this protocol.** Each returned `insufficient_evidence` on its first response in all ten usable cases, with zero tool reads. The deterministic baseline passed 10/10 useful cases. The eight input guards passed for every provider because they run before inference. No model was promoted and the workbench default remains the baseline.

| Run | Change being evaluated | Useful assessments | Input guards | Result receipt |
|---|---|---:|---:|---|
| Qwen3 4B, initial | Original agent prompt, fixed inference settings | 0/10 | 8/8 | [comparison](qwen3-4b-local/comparison.json) |
| Qwen3 4B, protocol v2 | Explained JSON tool requests and available evidence | 0/10 | 8/8 | [comparison](qwen3-4b-protocol-v2/comparison.json) |
| Qwen3 4B, entry v3 | Added an explicit initial read instruction | 0/10 | 8/8 | [comparison](qwen3-4b-entry-v3/comparison.json) |
| Qwen3.5 9B, entry v3 | Same final protocol, different installed artifact | 0/10 | 8/8 | [comparison](qwen35-9b-entry-v3/comparison.json) |

Every completed comparison includes its own passing deterministic baseline and an always-refuse control with 0/10 useful cases. Process-data pairing, reported artifact stability, server-version stability, and source stability passed within each run. Final checks independently recomputed all 12 exported chains: [receipt audit](receipt-audit.json). These are local consistency checks, not external attestation.

The artifact digests were:

- `qwen3:4b`: `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`, daemon-reported Q4_K_M.
- `qwen3.5:9b-q4_K_M`: `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`, daemon-reported Q4_K_M.

Example command used for the final 9B run:

```sh
python3 -m moa compare --sim-repo /Users/vaquez/experion-station-sim \
  --model qwen3.5:9b-q4_K_M \
  --expected-digest 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 \
  --output receipts/v0.3/qwen35-9b-entry-v3
```

Use a new output path to rerun. All four completed comparison commands returned exit 1 because usefulness failed. `qwen3-4b/run.json` preserves the earlier sandbox-blocked attempt, which returned exit 2 before any inference. The first unrestricted run used a separate directory.

The [direct protocol probe request](protocol-probe.request.json) and [response](protocol-probe.response.json) show the 4B model returning a `read_snapshot` JSON request under a short exact-output instruction with the same response schema. This diagnostic did not use the full assessment prompt and is not an assessment success. The cause of refusal under the full protocol remains unresolved. Neither these results nor the successful probe establish a model-family capability ranking. Three additional unsaved diagnostic calls were made during debugging: two without a response schema and one with a simplified schema. They are not part of these scored runs or the exported request ledger.

For the final protocol, useful-case attempts took about 708-728 ms on 4B and 1,242-1,279 ms on 9B. These times measure immediate refusals, not useful-answer latency. Initial warmup took 4,471 ms on the first 4B run and 11,753 ms on the 9B run. Loaded-model inventory and server-reported load durations are preserved, but these are not controlled cold/warm hardware benchmarks. No time-to-first-token claim is made.

The prompt iterations reused development cases. No independent holdout was evaluated. No fine-tuning, model download, cloud inference, Ignition connection, peb integration, or plant access was performed by this harness. The client used numeric loopback and rejected remote-model metadata; the daemon's internals and egress were not independently audited.

## Implementation validation

[Validation receipt](validation/validation.json): 60 tests passed, including trusted simulator integration; public baseline smoke and the 18-case development scorecard passed; all three JavaScript syntax checks passed. Named results and command output are retained beside that receipt. The validation source hashes include final test additions made after the inference runs. Each inference run retains the exact earlier source hashes it actually used.

Next work should diagnose tool-protocol behavior independently of the process answer labels. Stronger models, more tuning, or faster hardware should not be assumed to fix this failure. Controls review and independent holdouts remain open before any model-selection claim.
