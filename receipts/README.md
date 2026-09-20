# Validation receipts

The `v0.2/` directory contains the current time-series validation: actual command output, exit status, environment information, and SHA-256 hashes of the implementation, expectation manifest, and tests. `latest/` preserves the original v0.1 bootstrap run. Run from the repository root:

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

These receipts are local test evidence, not external attestation or a deployment approval. CI is configured but has not been run on a hosted service. Provider protocol checks use mocks; no actual model-quality result is claimed.
