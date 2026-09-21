# Master Operations Agent

An independent research workbench for an evidence-first operations advisor.

**Research workbench:** a local dashboard with sampled trends, a bounded agent loop, read-only observation tools, simulator exports, local-model comparisons, explicitly enabled DeepSeek synthetic experiments, and a hash-linked evidence log. The local provider preserves schema field order and receipts exact request-byte hashes. Python runtime dependencies and model downloads are not required.

This release assesses synthetic observations. Its default provider is a deterministic reference baseline. It is not a trained operations expert, an autonomous controller, or a plant-ready product.

**Outside reviewers:** start with the [external review handoff](docs/EXTERNAL_REVIEW_HANDOFF.md). It traces the repeated 0/10 useful-assessment results, confirmed harness defects, unresolved specification risks, and reproduction steps. The [latest public branch](https://github.com/templetwo/master-operations-agent/tree/main) includes the underlying failure receipts.

**v0.6 research:** [five-stage remediation and receipts](receipts/v0.6/README.md). A preregistered four-arm DeepSeek development experiment produced 0/10 accepted advisories unchanged, 0/10 with output guidance, 5/10 with complete policy guidance, and 4/10 with both. Stage-specific accounting and separate offline content diagnostics explain the differences. These are development results, not model promotion.

**Latest research, v0.7:** the frozen policy-only DeepSeek candidate achieved **7/24 useful answers** on the private synthetic holdout; the deterministic baseline achieved 24/24. All six guards passed. All 24 model answers completed required reads and passed envelope checks, but 17 failed content validation. The [preregistered campaign and aggregate receipts](receipts/v0.7/README.md) retain the failed acceptance result. The release validator and deterministic default remain unchanged. [Failure accounting](docs/failure-schema.md), [implementation provenance](docs/provenance.md), and the [separate explanation-task proposal](docs/next-explanation-task.md) describe the next research question.

**Local retest:** under a separately registered extension using the same policy-only prompt and private cases, **Qwen3 4B and Qwen3.5 9B each scored 0/24 useful answers**, with 6/6 guards and 24/24 required-read completion. Both completed without transport interruption; all candidates were withheld for shape or content failures. [Local results, comparison limits and audit](receipts/v0.7-local/README.md) preserve the failure rather than promote a model.

**Gemma follow-up:** `gemma4:12b-mlx` failed public schema enforcement, while `gemma4:12b-it-q4_K_M` GGUF passed. GGUF completed the public tool sequence but its advisory failed content validation. The [registered private comparison](receipts/v0.7-gemma-gguf/README.md) then stopped during its single warmup request, before any scored Gemma case. This is an incomplete benchmark, not 0/24 accuracy. [Public compatibility receipts](receipts/v0.7-gemma/README.md) remain separate, and no model was promoted.

## Start here

Python 3.10 or newer. From this checkout:

```sh
python3 -m moa serve
```

Open **http://127.0.0.1:8765**. Choose a scenario, assess it, inspect its evidence, and export the receipt chain. The server binds only to numeric loopback. Stop it with Ctrl+C.

Alternatively, double-click `Launch Workbench.command` on macOS. It starts the server and prints the URL.

```sh
python3 -m moa demo
python3 -m moa demo --scenario stale
python3 -m moa eval > smoke-report.json
python3 -m moa verify
python3 -m moa export > evidence-export.json
python3 -m unittest discover -s tests -v
```

The normal and cooling scenarios produce supported findings. Stale, incomplete, conflicting, or currently bad-quality observations are withheld before reaching a provider. The trend scenarios distinguish warming, falling temperature, unresolved cooling-path hypotheses, and unreliable history. The injection scenario keeps an instruction embedded in an alarm as evidence data. These are public development cases, not a general prompt-injection benchmark.

State lives in `.moa/evidence.sqlite3`, ignored by Git. Use `--store /path/to/research.sqlite3` to select a different store. Input and inference receipts may contain everything supplied to the agent; use synthetic data only.

## What is built

| Component | Behavior |
|---|---|
| Observation contract | Versioned JSON, known profiles, required tags and units, finite numbers, coherent timestamps, quality checks, complete alarm coverage |
| Agent loop | Six response turns maximum; tools are `read_snapshot`, `read_policy`, `read_tag`, and bounded `read_history` |
| Independent validator | Rechecks freshness after reasoning; validates findings, review checks, and evidence references |
| Operator output | Renders reviewed catalog text from validated IDs; never renders model-written control advice |
| Evidence | Records input, system prompt, provider responses, tool reads/denials, and outcome before releasing advice |
| Dashboard | Synthetic scenario selection, JSON import, tag-selectable trend plot, findings, evidence inspection and export |
| Simulator adapters | Export operator-visible snapshots and 120-second observation windows from separate headless instances |
| Development drills | Six recipes at two seeds and six integrity perturbations; explicit expectations and separate usefulness/guard scores |
| Provider options | Offline baseline by default; installed Ollama model or explicitly enabled DeepSeek synthetic comparison; no automatic fallback or model pull |
| Model comparison | Digest pinning, baseline and refusal controls, matched simulator data, durable progress, request and timing receipts |

The policy is intentionally small. The model must follow the read protocol and identify supported catalog findings. It does not yet perform open-ended root-cause analysis. The project thresholds are research sensitivities, not process design limits or alarm-standard requirements. The original demo thresholds are never applied to ESS tags. The new temporal policy retains explicit causal uncertainty and distinguishes falling temperature from complete recovery.

## Use your simulator

The exporter executes code from the trusted local `experion-station-sim` checkout. It starts its own synthetic instance; it does not connect to a running station. Node.js is required only for this adapter.

```sh
node scripts/export_sim.cjs /path/to/experion-station-sim normal > observation.json
python3 -m moa assess observation.json

node scripts/export_sim.cjs /path/to/experion-station-sim bad-quality > observation.json
python3 -m moa assess observation.json
```

Assess within 60 seconds of capture. Importing a file does not renew its timestamp. A stale file must be recaptured. The exporter records the Git revision and model ID, rejects tracked source modifications, and marks truncated alarm coverage as partial. `coachProjection()` is the observation source. Instructor state, hidden fault identifiers, and corrective-action answers are not exported.

Run the optional integration test against a trusted checkout:

```sh
MOA_SIM_REPO=/path/to/experion-station-sim python3 -m unittest discover -s tests -v
```

Export a time window or run the pinned development scorecard:

```sh
node scripts/export_trajectory.cjs /path/to/experion-station-sim cooling-loss 20260920 > window.json
python3 -m moa assess window.json
python3 -m moa drill-eval --sim-repo /path/to/experion-station-sim > drill-report.json
```

The agent receives no recipe names, fault schedule, seeds, instructor state, or expected answers. The scorecard retains that metadata separately. The baseline passes 18 development cases, and the always-refuse control fails usefulness. These are project-authored cases with controls review pending. See [the drill contract and limits](docs/drills.md).

## Try an installed local model

The provider uses Ollama's documented chat and structured-output interfaces. Sources and read dates are in [docs/sources.md](docs/sources.md). No Ollama request happens unless you supply `--model`.

Configure your trusted Ollama daemon for local-only operation, disable its cloud features, and control its network egress. A loopback client cannot prove what a server does internally. The Ollama provider refuses cloud-named and remote-metadata models, uses `127.0.0.1`, ignores proxy variables, does not follow redirects, and has no download or fallback path.

Use the **exact installed name including its tag**. The following placeholder is not a model recommendation:

```sh
python3 -m moa demo --model 'YOUR_INSTALLED_MODEL:TAG'
python3 -m moa eval --model 'YOUR_INSTALLED_MODEL:TAG' > local-model-smoke.json
python3 -m moa serve --model 'YOUR_INSTALLED_MODEL:TAG'
```

The provider checks installed metadata, pins the first accepted digest for its lifetime, and records the requested settings and template hash. Each HTTP operation has a 20-second socket timeout and bounded response size; the agent has a six-turn limit and a 60-second observation freshness budget. A slow model may produce a valid candidate that is withheld because its observation expired. This version does not stream tokens or measure time to first token.

For a reproducible development comparison, supply the installed artifact's exact digest:

```sh
python3 -m moa compare --sim-repo /path/to/experion-station-sim \
  --model 'YOUR_INSTALLED_MODEL:TAG' --expected-digest 'EXACT_64_CHARACTER_DIGEST' \
  --output receipts/my-new-comparison
```

The output directory must be new. Baseline, always-refuse, and actual model results are reported separately. Failed runs are retained. See [the comparison contract](docs/local-evaluation.md), [the serialization bug and fix](docs/protocol-order.md), and [actual v0.4 development results](receipts/v0.4/README.md). The earlier v0.3 comparisons used a defective schema serializer and remain preserved as debugging evidence. The default workbench remains on the deterministic baseline.

## Evidence and evaluation

An optional [DeepSeek API comparison](docs/deepseek.md) is available through `compare-deepseek`. It requires an explicit credential-file path and `--allow-cloud-synthetic`, uses only generated simulator cases, and leaves the dashboard and default provider local. The first actual run completed required reads on 10/10 usable cases but produced 0/10 accepted advisories. [Its original receipts](receipts/v0.5/deepseek-live-network/README.md) remain unchanged. The separate [preregistered guidance experiment](docs/guidance-experiment.md) now isolates format instructions from complete policy mapping; [all four actual outcomes](receipts/v0.6/guidance-live/README.md) are retained, including failures.

`verify` checks chain consistency. Export the `anchor` object to a separate location if you need to detect truncation or whole-history replacement, then pass that JSON object as `verify --anchor saved-anchor.json`. An unanchored local hash chain is not independent attestation. This implementation is not peb and does not claim peb authorization or review integration.

The public evaluation reports useful assessments and input-guard results separately. Its always-refuse negative control fails. Guard refusals do not count as voluntary model abstention. Full run events accompany the report so the numbers can be inspected.

New runs record the terminal failure stage and reconcile every withheld case. Candidate shape/content rejection totals exclude input and tool-protocol failures. Historical rows lacking stage metadata remain explicitly unclassified, not retrospectively relabeled. [Offline diagnostics](docs/diagnostics.md) independently verify report chains and compare proposed IDs with authored expectations, without changing release decisions or calling the policy oracle.

See [architecture and boundaries](docs/architecture.md), [the build sequence](docs/roadmap.md), and [validation receipts](receipts/README.md).

## Next build

Investigate remaining unsupported finding selection using the separated diagnostics. The local 9B baseline result remains 0/10; the policy-guided cloud configuration reached 5/10 on the reused development set and is not promoted. [Private holdout preparation](docs/holdout-protocol.md) separates authoring and agent review from tuning, with exposure limits disclosed. Independent controls-engineer review remains open. Ignition ingestion, peb integration, plant procedures, training, hardware purchases, and any real-plant work remain separate gates.
