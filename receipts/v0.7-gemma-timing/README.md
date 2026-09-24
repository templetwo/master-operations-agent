# Public Gemma startup timing

All six public protocol requests returned the correct first `read_snapshot` tool request. One unloaded request exceeded the original 20-second timeout; all loaded requests finished below two seconds. Under the rule published before inference, this supports proposing a **60-second warmup allowance in a separate future registration**. No provider setting or benchmark limit has been changed, and the previous incomplete campaign remains intact.

| Pair | Unloaded wall time | Loaded wall time | Correct first read |
|---|---:|---:|---|
| 1 | 22.289 s | 1.598 s | Both |
| 2 | 18.405 s | 1.424 s | Both |
| 3 | 11.619 s | 1.387 s | Both |

These are complete nonstreaming request times, not time to first token or operations-advice latency. This diagnostic never supplied an observation or tool result and does not measure usefulness or abstention.

## Why a separate warmup budget is supported

The registered rule required all six correct replies, all loaded requests at or below 20 seconds, and at least one unloaded request above 20 seconds. It selects the smallest of 60 or 120 seconds with at least 1.5 times the slowest unloaded duration. All conditions held: the maximum was 22.28914 seconds unloaded and 1.59781 seconds loaded. The 1.5x margin and available budget choices are engineering choices, not statistical guarantees.

The daemon reported load durations of 12.312, 8.485 and 1.875 seconds for unloaded members, plus approximately 8.7–8.8 seconds of prompt processing each. Loaded members reported 0.268–0.343 seconds of loading and 0.093–0.130 seconds of prompt processing. Generation took roughly one second throughout. These self-reported components support an explanation involving startup and prompt-processing costs, but cannot establish the cause of the earlier campaign's generic provider error.

The actual measurement caller used a **120-second socket timeout** to observe requests beyond the old cutoff. The retained provider metadata still says 20 seconds because it records the unchanged production adapter configuration. Request bodies match that adapter byte for byte; only this diagnostic's HTTP timeout differs. The scored-request timeout remains 20 seconds and observation freshness remains 60 seconds.

## Receipts and checks

- [Published protocol](../../docs/gemma-warmup-timing.md) and [registration](preregistration.json), committed as [e0d3a53](https://github.com/templetwo/master-operations-agent/commit/e0d3a53a9e024c1e04521082c5c28753b3f4951c) before inference.
- [Publication check](publication-check.json): anonymous registration bytes matched before the run. Registration SHA-256: `8a1ae8cdfcc90de76da3654ede50bc10cf98bd749e0bca190e5ac5be50064cd2`.
- [Run and recommendation](run/run.json), [pair 1](run/pair-1), [pair 2](run/pair-2), and [pair 3](run/pair-3). Each attempt retains exact request/response bytes and hashes, the parsed response, timestamps and reported timing fields.
- [Separate agent's public audit](audit.json): all six request/response pairs, 48 source hashes, registered inputs, residency checks and fixed recommendation verified without more inference. This is same-team review of local evidence, not external attestation.

The run took place on September 23 local time, from **2026-09-24T00:38:25.416Z to 00:39:22.855Z**. It used the pinned Gemma 4 12B GGUF Q4_K_M artifact on an Apple M3 Pro with 18 GiB memory and Ollama 0.32.6. Six completion requests and two targeted unload commands were made; the first pair began with an empty daemon inventory. No retries, downloads, cloud calls or private-case reads occurred. Model metadata, source and registered inputs remained unchanged. All 133 tests passed including the trusted simulator; [CI](https://github.com/templetwo/master-operations-agent/actions/runs/35938895482) also passed.

## Limits and next step

Unloaded means absent from Ollama's reported memory inventory. OS file caches were not cleared, hardware was not rebooted, and exclusive machine or daemon use was not established. The falling unloaded durations show why these three pairs are not a reliable worst-case estimate. Loaded requests also reuse the identical prompt, so residency and prompt caching are confounded. The response did not include an explicit cached-token count; it must not be assumed to be zero. This is a small, fixed-order diagnostic, not externally attested inference or a model-capability benchmark.

The next candidate configuration would allow 60 seconds for its single public warmup, then retain 20 seconds per scored request, 60-second observation freshness, the original policy/validator, and one attempt per case. It needs a new registration and a distinct campaign record that preserves the failed 20-second attempt. **This timing task did not execute that campaign or promote Gemma.**
