# Local model development comparisons

This is a development harness, not a model promotion gate. The simulator cases are public and their expected answers have not had independent controls review. Prompt changes made after observing a run are development tuning. Scores on these same cases are not held-out estimates.

## Run a pinned comparison

Use a trusted simulator checkout and an exact model already installed in the local Ollama service. Read its digest from that service's `/api/tags` response. No command here pulls a model or chooses a cloud provider.

```sh
python3 -m moa compare \
  --sim-repo /path/to/experion-station-sim \
  --model 'YOUR_INSTALLED_MODEL:TAG' \
  --expected-digest 'EXACT_64_CHARACTER_DIGEST' \
  --output receipts/my-new-comparison
```

The output directory must be new. Exit 0 means the local candidate passed this development suite and comparison integrity checks. Exit 1 means the comparison completed but did not meet those conditions. Exit 2 means setup or execution failed. Neither exit 0 nor an intact evidence chain grants promotion or plant authority.

The harness runs the deterministic baseline, an always-refuse control, and the selected model. Each receives separately generated fresh observations from the same recipes and seeds. Original capture timestamps remain intact. Matching process-data hashes exclude only capture times, snapshot IDs, tag observation times, and simulation epoch IDs. The original inputs and evaluator expectations remain in the receipts. Integrity checks reject a mismatched pair or a change in source files, reported artifact metadata, or reported server version during the run.

Model preparations check the pinned digest before every usable assessment and after the suite. A tag could change between checks, and a malicious daemon could misreport its identity. These checks do not provide signed artifact attestation or enforce daemon egress controls.

## What is recorded

- `run.json`: source hashes, manifest and policy hashes, prompt hashes, hardware, serving version, artifact metadata and fixed settings. An incomplete run remains marked interrupted or running.
- `warmup.json`: one explicit protocol warmup before scored local captures. Loaded model names and digests before the run are in `run.json`. No model is unloaded to manufacture a cold measurement.
- `baseline.json`, `always-refuse.json`, `local-model.json`: case results, expected findings, original observations, model candidates, tool reads, validation decisions, and evidence anchors.
- `*.progress.jsonl` and local `*.sqlite3`: completed-case checkpoints and durable events. SQLite files are Git-ignored; the JSON reports carry exportable chains.
- `comparison.json`: integrity results, separate usefulness and input-guard scores, model abstentions, candidate rejections, and inference counters.

Requests use temperature 0, seed 0, context 8192, output budget 768, `think: false`, and non-streaming responses. These are requested settings, not proof of deterministic inference or proof that the backend applies every option. The client records semantic request hashes, exact request-byte hashes, the returned response hash, bounded visible content, wall time, and available daemon timing/token counters. It does not retain a separate reasoning field. Missing counters remain unknown. Time to first token is unmeasured.

V0.4 preserves schema declaration order on the wire. The v0.3 encoder sorted it, biasing constrained output toward abstention in a reproducible local diagnostic. The schema values and semantic hash are unchanged by reordering, which is why exact byte hashes now accompany semantic hashes. See [the diagnosis and controlled experiment](protocol-order.md). Old results remain labeled by the exact implementation they used.

Each socket operation has a 20-second timeout. The agent still has six response turns and a 60-second observation freshness budget. A socket timeout is not a hard whole-run deadline. A cold load or slow response may withhold an otherwise valid candidate. Warmup results are excluded from scored-case inference totals. Aggregate end-to-end time across all 18 cases includes eight cheap boundary refusals; use per-case timings when judging useful-answer latency.

## Interpretation

Eight invalid inputs are refused by deterministic guards before a model runs. Those successes do not measure learned abstention. Ten usable cases measure whether the model requests the required evidence and supplies exactly supported findings, checks, and citations. The validator can suppress a bad candidate, so count candidate rejections alongside released advice. Zero released bad advice is not proof that the model never proposed an unsupported answer.

The deterministic policy already solves this narrow catalog task. Matching it is an integration milestone, not evidence that an LLM adds reasoning value. Keep the default workbench on the baseline until broader independent evaluation demonstrates a reason to change it.

## Interface receipts

The chat API documents structured formats, the thinking control, completion fields, and duration/token counters: [Ollama chat API](https://docs.ollama.com/api/chat), read 2026-09-20. Thinking controls are model-dependent: [Ollama thinking documentation](https://docs.ollama.com/capabilities/thinking), read 2026-09-20. These sources describe interfaces, not measured behavior of this daemon. Local behavior is established only by the accompanying run receipts.
