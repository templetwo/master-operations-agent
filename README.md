# Master Operations Agent

An independent research workbench for an evidence-first operations advisor.

**Working v0.1:** a local dashboard, bounded agent loop, read-only observation tools, a simulator export, an optional Ollama provider, and a hash-linked evidence log. It runs without downloading a model or installing Python runtime dependencies.

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

The normal and cooling scenarios produce supported findings. Stale, incomplete, conflicting, or bad-quality observations are withheld before reaching a provider. The injection scenario keeps an instruction embedded in an alarm as evidence data. These are public smoke cases, not a general prompt-injection benchmark.

State lives in `.moa/evidence.sqlite3`, ignored by Git. Use `--store /path/to/research.sqlite3` to select a different store. Input and inference receipts may contain everything supplied to the agent; use synthetic data only.

## What is built

| Component | Behavior |
|---|---|
| Observation contract | Versioned JSON, known profiles, required tags and units, finite numbers, coherent timestamps, quality checks, complete alarm coverage |
| Agent loop | Six response turns maximum; tools are `read_snapshot`, `read_policy`, and `read_tag` |
| Independent validator | Rechecks freshness after reasoning; validates findings, review checks, and evidence references |
| Operator output | Renders reviewed catalog text from validated IDs; never renders model-written control advice |
| Evidence | Records input, system prompt, provider responses, tool reads/denials, and outcome before releasing advice |
| Dashboard | Synthetic scenario selection, JSON import, observed values, findings, evidence inspection and export |
| Simulator adapter | Exports the operator-visible projection from a separate headless simulation instance |
| Provider options | Offline baseline by default; explicitly selected installed Ollama model; no cloud fallback or model pull |

The v0.1 policy is intentionally small. The model must follow the read protocol and identify supported catalog findings. It does not yet perform open-ended root-cause analysis. The cooling thresholds belong to the authored demo; they are not process design limits or alarm-standard requirements. The ESS profile reports alarms without applying the demo thresholds to ESS tags.

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

## Try an installed local model

The provider uses Ollama's documented chat and structured-output interfaces. Sources and read dates are in [docs/sources.md](docs/sources.md). No Ollama request happens unless you supply `--model`.

Configure your trusted Ollama daemon for local-only operation, disable its cloud features, and control its network egress. A loopback client cannot prove what a server does internally. This repository refuses cloud-named and remote-metadata models, uses `127.0.0.1`, ignores proxy variables, does not follow redirects, and has no download or fallback path.

Use the **exact installed name including its tag**. The following placeholder is not a model recommendation:

```sh
python3 -m moa demo --model 'YOUR_INSTALLED_MODEL:TAG'
python3 -m moa eval --model 'YOUR_INSTALLED_MODEL:TAG' > local-model-smoke.json
python3 -m moa serve --model 'YOUR_INSTALLED_MODEL:TAG'
```

The provider checks installed metadata and records the reported digest. Each HTTP operation has a 20-second socket timeout and bounded response size; the entire agent has a six-turn limit and a 60-second observation freshness budget. A slow model may produce a valid candidate that is withheld because its observation expired. This version does not stream tokens or measure time to first token. No actual model inference was used to validate v0.1; provider transport tests use mocks.

## Evidence and evaluation

`verify` checks chain consistency. Export the `anchor` object to a separate location if you need to detect truncation or whole-history replacement, then pass that JSON object as `verify --anchor saved-anchor.json`. An unanchored local hash chain is not independent attestation. This implementation is not peb and does not claim peb authorization or review integration.

The public evaluation reports useful assessments and input-guard results separately. Its always-refuse negative control fails. Guard refusals do not count as voluntary model abstention. Full run events accompany the report so the numbers can be inspected.

See [architecture and boundaries](docs/architecture.md), [the build sequence](docs/roadmap.md), and [validation receipts](receipts/README.md).

## Next build

Add a held-out, time-series simulator evaluation with controls-engineer-reviewed expected findings. That gives us a useful measure for choosing and improving a local model. Ignition ingestion, peb integration, plant procedures, model tuning, hardware purchases, and any real-plant work remain separate gates. No plant address, credentials, control executor, or arbitrary script tool is present in this release.
