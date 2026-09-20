# V0.4: protocol failure isolated and repaired

Recorded 2026-09-20. The premature refusals were caused by an order-sensitive integration bug in our request encoder. Recursively sorting the response schema changed its generated-output ordering. The fix preserves schema declaration order while leaving canonical evidence hashing intact. A second change explicitly reports unread required tools after each tool result.

**The final 9B run completed the required read protocol on 10/10 usable cases. Its answer-quality score remains 0/10, and every invalid candidate was withheld.** The deterministic baseline stays the workbench default. No local model is promoted.

## Controlled diagnosis

[Schema-order-only experiment](schema-order-4b/run.json): the same pinned 4B artifact received identical JSON values, prompt, settings, and schema constraints. Only schema property order changed. The sequence sorted, declared, declared, sorted produced abstain, read_snapshot, read_snapshot, abstain. Each exact request and response is retained in that directory. No process data or process answer labels were used, and no tools executed.

[Initial whole-request order experiment](serialization-4b/run.json) produced the same pattern. [Independent receipt audit](receipt-audit.json) verifies hashes against the actual saved bytes and confirms semantic equality of the request bodies. [Diagnosis and source explanation](../../docs/protocol-order.md) describes why a semantic hash alone could not detect the difference.

## Development comparisons

Each run uses the same pinned simulator, expectation manifest, policy, and independent candidate validator as v0.3. Changes to the transport and later protocol-status messages are recorded by each run's source and prompt hashes. Artifact pins and hardware metadata are in its `run.json`.

| Run | Completed all required reads | Useful assessments | Input guards | Receipt |
|---|---:|---:|---:|---|
| 4B, serialization fix only | 0/10 | 0/10 | 8/8 | [comparison](qwen3-4b/comparison.json) |
| 9B, serialization fix only | 0/10 | 0/10 | 8/8 | [comparison](qwen35-9b/comparison.json) |
| 9B, serialization fix plus read status | 10/10 | 0/10 | 8/8 | [comparison](qwen35-9b-read-state/comparison.json) |

With serialization fixed, the 4B model read snapshot and policy in every usable case but omitted history. The 9B model read the snapshot in every usable case and policy in two. Both attempted advice and were rejected as ungrounded. With explicit protocol status, the 9B model requested snapshot, policy, and history in all ten cases. It then produced nine incomplete candidate structures, including empty check lists, and one unsupported finding set. The guard against these errors was unchanged.

These read-completion counts are derived from `tool_read` events, not inferred from a model's claim that it read evidence. The [audit](receipt-audit.json) includes the derivation and verifies all nine exported comparison chains. Each comparison includes a deterministic baseline with 10/10 useful assessments and an always-refuse control with 0/10. The eight input guards execute before the model and are not model-quality scores. All comparison integrity checks passed. Each comparison command exited 1 because useful assessment failed, despite the protocol improvement.

The actual artifacts remained:

- `qwen3:4b`, digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
- `qwen3.5:9b-q4_K_M`, digest `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`.

The final 9B run used 40 scored inference calls. Usable-case attempts took 16.09 to 21.42 seconds, median 19.72 seconds. These are timings of withheld candidates, not useful-answer latency. No streaming or time-to-first-token measurement was added. Hardware remained the M3 Pro with 18 GiB and the daemon reported `0.32.6`; these are local observations, not independent backend attestation.

## Reproduce

Use a new output directory:

```sh
python3 scripts/probe_serialization.py --model qwen3:4b \
  --expected-digest 359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7 \
  --output receipts/new-order-probe

python3 -m moa compare --sim-repo /Users/vaquez/experion-station-sim \
  --model qwen3.5:9b-q4_K_M \
  --expected-digest 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 \
  --output receipts/new-development-comparison
```

The current script and application use the final prompt. The earlier diagnostic directories retain the exact earlier prompt bytes they tested. Regeneration is a new measurement, not a guarantee of byte-identical model output.

## Validation and remaining work

[Implementation validation](validation/validation.json): 63 tests passed, including simulator integration. The public smoke suite, 18-case baseline scorecard, and three JavaScript syntax checks also passed. The receipt records final source hashes and command output. The suite covers the HTTP wire ordering regression, semantic versus byte hashing, non-finite JSON rejection, remaining-read state without answer IDs, continued abstention availability, skipped-read rejection, freshness and scope guards, and simulator integration.

The next question is supported finding and check selection after evidence is available. Diagnose evidence presentation and inference settings on separate development tasks before considering training. Neither this transport fix nor completing reads demonstrates process reasoning competence. No held-out evaluation or controls-engineer review was performed, and no validator, policy threshold, or expected answer was relaxed. No new model, cloud provider, plant connection, or write tool was introduced.
