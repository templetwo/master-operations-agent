# Master Operations Agent

An independent research workbench for an evidence-first operations advisor.

**Working v0.2:** a local dashboard with sampled trends, a bounded agent loop, read-only observation tools, snapshot and time-series simulator exports, a development drill scorecard, an optional Ollama provider, and a hash-linked evidence log. It runs without downloading a model or installing Python runtime dependencies.

This release assesses synthetic observations. Its default provider is a deterministic reference baseline. It is not a trained operations expert, an autonomous controller, or a plant-ready product.

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
| Provider options | Offline baseline by default; explicitly selected installed Ollama model; no cloud fallback or model pull |

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

Configure your trusted Ollama daemon for local-only operation, disable its cloud features, and control its network egress. A loopback client cannot prove what a server does internally. This repository refuses cloud-named and remote-metadata models, uses `127.0.0.1`, ignores proxy variables, does not follow redirects, and has no download or fallback path.

Use the **exact installed name including its tag**. The following placeholder is not a model recommendation:

```sh
python3 -m moa demo --model 'YOUR_INSTALLED_MODEL:TAG'
python3 -m moa eval --model 'YOUR_INSTALLED_MODEL:TAG' > local-model-smoke.json
python3 -m moa serve --model 'YOUR_INSTALLED_MODEL:TAG'
```

The provider checks installed metadata and records the reported digest. Each HTTP operation has a 20-second socket timeout and bounded response size; the entire agent has a six-turn limit and a 60-second observation freshness budget. A slow model may produce a valid candidate that is withheld because its observation expired. This version does not stream tokens or measure time to first token. No actual model inference was used to validate v0.2; provider transport tests use mocks.

## Evidence and evaluation

`verify` checks chain consistency. Export the `anchor` object to a separate location if you need to detect truncation or whole-history replacement, then pass that JSON object as `verify --anchor saved-anchor.json`. An unanchored local hash chain is not independent attestation. This implementation is not peb and does not claim peb authorization or review integration.

The public evaluation reports useful assessments and input-guard results separately. Its always-refuse negative control fails. Guard refusals do not count as voluntary model abstention. Full run events accompany the report so the numbers can be inspected.

See [architecture and boundaries](docs/architecture.md), [the build sequence](docs/roadmap.md), and [validation receipts](receipts/README.md).

## Next build

Review the development drill expectations with a controls engineer, then freeze independent holdouts before comparing local models. The time-series exporter and scorecard are now implemented; the independent review and actual model comparison are still open. Ignition ingestion, peb integration, plant procedures, model tuning, hardware purchases, and any real-plant work remain separate gates. No plant address, credentials, control executor, or arbitrary script tool is present in this release.
