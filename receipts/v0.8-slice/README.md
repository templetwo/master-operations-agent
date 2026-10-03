# v0.8 slice receipts

The [slice report](../../docs/v0.8-slice-report.md) is the index for this directory. Its "Commands and measured acceptance" section lists the commands that produced `validation-clean/`, `tests.json` and `cli-proof.json`. The producers are `scripts/run_slice.cjs`, `scripts/validate_slice.py`, `scripts/check_slice.py` and `scripts/profile_evidence.py`.

- `validation-clean/validation.json` is the current validation pointer in [`receipts/current.json`](../current.json).
- `tests.json` holds the final T1 to T11 outcomes. `tests-initial.json`, `initial-index.json` and `validation-01/` preserve the first, failed acceptance run.
- The report ran its commands in `/private/tmp` checkouts that no longer exist. To recreate one, clone the repository and check out the named revision.

Added 2026-10-03 by the MacBook seat (claude-opus-5-5). The receipts in this directory were not changed.
