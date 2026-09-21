# Change log

## 0.7.0

- Unify distribution and HTTP version reporting through `moa.__version__`.
- Add a credential placeholder, failure-accounting contract and additive Codex provenance.
- Permit an explicit bounded DeepSeek campaign call cap, keeping the default 61-call development limit and unchanged generation settings.
- Run a single preregistered policy-only private holdout campaign: 7/24 useful model answers versus 24/24 deterministic baseline, with 6/6 guards. The acceptance gate failed; no model was promoted. Public aggregate results are separate from private case-level evidence.
- Define the separate cited-explanation research question without implementing a new agent task.

## 0.6 research series

Stage-specific failure accounting, independent offline receipt diagnostics, complete optional policy guidance, a preregistered four-arm development experiment, and a reviewed private holdout freeze. See [the preserved receipts](receipts/v0.6/README.md). Historical distribution and HTTP version strings lagged this research series; 0.7.0 resolves that drift without rewriting old records.
