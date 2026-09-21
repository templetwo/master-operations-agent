# Change log

## 0.7.0

- Unify distribution and HTTP version reporting through `moa.__version__`.
- Add a credential placeholder, failure-accounting contract and additive Codex provenance.
- Permit an explicit bounded DeepSeek campaign call cap, keeping the default 61-call development limit and unchanged generation settings.
- Prepare a single policy-only private holdout campaign. Publication of the preregistration precedes evaluation; results are recorded separately from implementation and do not automatically promote a model.
- Define the separate cited-explanation research question without implementing a new agent task.

## 0.6 research series

Stage-specific failure accounting, independent offline receipt diagnostics, complete optional policy guidance, a preregistered four-arm development experiment, and a reviewed private holdout freeze. See [the preserved receipts](receipts/v0.6/README.md). Historical distribution and HTTP version strings lagged this research series; 0.7.0 resolves that drift without rewriting old records.
