# Change log

## 0.8.0

- Add the v0.8 provider-free stream boundary and deterministic slice: schema 1.2 subject-only observations and dependency-scoped `lab-v2-deps` findings. All eleven acceptance tests pass from a clean checkout. The legacy advisor is unchanged. See [the slice report](docs/v0.8-slice-report.md).
- Carry uncertain source quality through the stream and legacy adapters without using it for findings that need Good values. Snapshot schema 1.3 exports SP, OP and categorical MODE; `--legacy` keeps schema 1.0 output (PR #1).
- Record the source-map v2 re-score: the v1 drill expectations give 8/10 useful and 8/8 guards against simulator `bfed001`, because cooling-loss drives TIC202 above its declared range and the advice gate withholds advice on the uncertain reading. The 10/10 result stays pinned to simulator `3aad769`.
- Add `scripts/rescore_drills.py`, which scores any development manifest against a simulator checkout with deterministic providers, records an explicit revision override, and compares rows with a recorded receipt. It reproduces the source-map v2 rows with 0 mismatches.
- Add `moa/data/drills-v2.json`, pinned to simulator `bfed001`, with cooling-loss expected to abstain for quality. `drills-v1.json` and every experiment pin are unchanged. Baseline 8/8 useful and 10/10 guards; always-refuse 0/8 and 10/10. Simulator integration tests now select the manifest pinned to the checkout under test.
- Add missing receipt READMEs for the v0.8 intake and slice, and correct the stale validation-output note in the receipts index.
- Freeze the cited-explanation contract in `docs/explanation-task-v1.md`. No cases, runner, model call, new tool, or promotion threshold.

## 0.7.0

- Unify distribution and HTTP version reporting through `moa.__version__`.
- Add a credential placeholder, failure-accounting contract and additive Codex provenance.
- Permit an explicit bounded DeepSeek campaign call cap, keeping the default 61-call development limit and unchanged generation settings.
- Run a single preregistered policy-only private holdout campaign: 7/24 useful model answers versus 24/24 deterministic baseline, with 6/6 guards. The acceptance gate failed; no model was promoted. Public aggregate results are separate from private case-level evidence.
- Define the separate cited-explanation research question without implementing a new agent task.

## 0.6 research series

Stage-specific failure accounting, independent offline receipt diagnostics, complete optional policy guidance, a preregistered four-arm development experiment, and a reviewed private holdout freeze. See [the preserved receipts](receipts/v0.6/README.md). Historical distribution and HTTP version strings lagged this research series; 0.7.0 resolves that drift without rewriting old records.
