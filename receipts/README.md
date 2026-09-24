# Validation receipts

Start with the [public Gemma startup timing](v0.7-gemma-timing/README.md), [incomplete Gemma comparison](v0.7-gemma-gguf/README.md), [Qwen local comparisons](v0.7-local/README.md), and [DeepSeek private-corpus aggregate](v0.7/README.md). Each records its own scope, frozen configuration and limits. The [v0.6 index](v0.6/README.md) records the earlier guidance experiment and holdout preparation.

The `v0.5/` directory preserves DeepSeek authentication attempts and validation from that revision. `v0.4/` contains schema-order diagnostics and corrected local-model comparisons. `v0.3/` preserves comparisons affected by the schema serialization bug. `v0.2/` preserves time-series validation. Despite its name, **`latest/` is the original v0.1 bootstrap archive**, not current validation. Preserve its bytes.

Use an explicitly new output directory when running validation. The current script still defaults to the historical `latest/` path and does not enforce a fresh destination; that pending harness fix is recorded in the [v0.8 intake](../docs/v0.8-intake.md). Run from the repository root:

```sh
python3 scripts/validate.py --sim-repo /path/to/experion-station-sim --output receipts/new-run
```

Omit `--sim-repo` to run without the optional simulator integration. The unittest output explicitly reports that skip. The script also needs Node.js for JavaScript syntax checks.

- `check-1.stderr`: named unittest results, including boundary and HTTP checks.
- `check-2.stdout`: public baseline evaluation with all run events and an evidence anchor.
- `check-3.*`, `check-4.*`, and `check-5.*`: JavaScript syntax checks.
- `check-6.stdout`: the v0.2 development drill scorecard, included when a simulator checkout is supplied.
- `validation.json`: exact commands, environment, outcomes, and source hashes.
- `browser-check.md`: original tool-observed v0.1 browser verification.
- `v0.2/browser-check.md`: trend selection, plotted units, supported thermal assessment, and limited unreliable-history assessment checked in Comet.

These receipts are local test evidence, not external attestation or a deployment approval. Hosted CI has run successfully, including the [timing-diagnostic source validation](https://github.com/templetwo/master-operations-agent/actions/runs/35938895482). Unit provider checks use mocks; separately labeled model campaigns and public probes identify actual inference. Successful tests do not establish model usefulness or engineering validity.
