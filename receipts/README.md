# Validation receipts

The `latest/` directory contains actual command output, exit status, environment information, and SHA-256 hashes of the implementation and tests that were checked. Run from the repository root:

```sh
python3 scripts/validate.py --sim-repo /path/to/experion-station-sim
```

Omit `--sim-repo` to run without the optional simulator integration. The unittest output explicitly reports that skip. The script also needs Node.js for JavaScript syntax checks.

- `check-1.stderr`: named unittest results, including boundary and HTTP checks.
- `check-2.stdout`: public baseline evaluation with all run events and an evidence anchor.
- `check-3.*` and `check-4.*`: JavaScript syntax checks.
- `validation.json`: exact commands, environment, outcomes, and source hashes.
- `browser-check.md`: manually recorded, tool-observed browser verification.

These receipts are local test evidence, not external attestation or a deployment approval. CI is configured but has not been run on a hosted service. Provider protocol checks use mocks; no actual model-quality result is claimed.
