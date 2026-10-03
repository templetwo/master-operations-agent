# Reproducing the source-map v2 evaluation

Added 2026-10-03 by the MacBook seat (claude-opus-5-5) on `Anthonys-MacBook-Pro.local`. The [README](README.md) and [evaluation.json](evaluation.json) beside this file are the original record and were not edited.

The original record does not name the command that produced it, and no producer was committed with it. `moa.drills.evaluate_drills` refuses a simulator checkout that is not at the manifest pin, so the run must have bypassed that check. [`scripts/rescore_drills.py`](../../scripts/rescore_drills.py) now does the same thing explicitly and records the override in its output.

```sh
git clone ~/experion-station-sim /tmp/sim-bfed001
git -C /tmp/sim-bfed001 checkout bfed001fc89d9beaa640b30a7886d5f16f61a31b
python3 scripts/rescore_drills.py /tmp/sim-bfed001 --manifest moa/data/drills-v1.json \
  --allow-revision-mismatch --compare receipts/source-map-v2/evaluation.json --out /tmp/source-map-v2-rescore.json
```

Paths are shown as `/tmp`; the recorded run used throwaway clones of the same revision in a job scratch directory.

Actual result on 2026-10-03, MOA branch `claude/stage-hardening`, Node v22.23.2, Python 3.10.12, deterministic baseline, 0 models called:

```
ess-u1-development-v1 at bfed001: useful 8/10, guards 8/8, 0 mismatches against receipts/source-map-v2/evaluation.json
```

The comparison covers all 18 rows: `passed`, expected and actual status, reason and finding ids, `process_data_sha256`, and `evidence_fidelity`. The recorded per-row `tic202` value is not compared, because the scorecard rows do not carry the observation. The simulator source explains it: `src/measurement.js` at `5b269fb` declares TIC202 as 0 to 100 °C with a reporting limit of 103.125, and marks clamped values `Uncertain_EngineeringUnitsExceeded`.

`tests/test_rescore_drills.py` runs the same comparison when `MOA_SIM_REPO` points at a clean `bfed001` checkout, and skips otherwise.
