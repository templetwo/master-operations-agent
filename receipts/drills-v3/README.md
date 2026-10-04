# Development drills v3 at simulator adeb18a

Recorded 2026-10-04 by the HQ seat's build lane (claude-opus-5-5) on `mac-studio`. Deterministic providers only. Models called: 0.

[`moa/data/drills-v3.json`](../../moa/data/drills-v3.json) (sha256 `67bd47aa9f744812f4665693e4295437ea02298d79dd9b943f7a633226fc0170`) is a new development manifest pinned to simulator `adeb18a92de942ed1a60bcf4112430baa071c89d`, whose `src/model-id.js` reads `8a6e92919c5e25e60ddfe25cc5fe1462d9da7ce9040adbf670631a1e89bf7da8`. The manifest has no model id field, as in v2; the exporter records the model id with every observation. v3 is derived from `drills-v2.json` (sha256 `165e12c7…`, pinned to `bfed001`), which is unchanged. `drills-v1.json` is unchanged and remains the pin for every existing experiment module.

One expectation changed. At `adeb18a` TIC201 rises much less across the restoration-lag window than at `bfed001`:

| Seed | `bfed001`, first to last TIC201 | `adeb18a`, first to last TIC201 |
| --- | --- | --- |
| 20260920 | 172.7 to 176.9 °C (+4.2) | 172.3 to 173.0 °C (+0.7) |
| 20260921 | 172.6 to 176.9 °C (+4.3) | 172.2 to 173.0 °C (+0.8) |

The `reactor_warming` rule in `moa/knowledge.py` needs a rise of at least 2 °C, so it no longer fires. Both seeds are still supported advisories with `reported_alarms` and `cause_unresolved` and the same two checks. v3 expects that advisory without `reactor_warming`. Every other case is byte-identical to v2.

| Run | Useful assessment | Input guards | Voluntary abstentions | Receipt |
| --- | --- | --- | --- | --- |
| Deterministic baseline | 8/8 | 10/10 | 0 | [baseline.json](baseline.json), sha256 `3dc51f051275dd18087ab87b9f0ae45e2cc4ca64ac96ddb86d8561b83655052d` |
| Always-refuse negative control | 0/8 | 10/10 | 8 | [always-refuse.json](always-refuse.json), sha256 `4cc4b8b8de472876e856feb74e710ff8bade896825a8ce2657fc2bfacdcdd3ef` |

**Coverage cost.** In v2 the two restoration-lag seeds were the only development cases that expected `reactor_warming`. In v3 no development case expects it, and the baseline emits it on none. Unit tests on public fixtures still exercise the rule (for example `tests/test_history.py` and the trend-cooling golden in `tests/test_explanation_freeze.py`), but no simulator export in the development scorecard does. Whether a restoration-lag window can be exported at this revision with a TIC201 rise of 2 °C or more is an open question for a later manifest.

**Cause.** The simulator's credibility-pass stage S1 (spec section 2.4) routes each point's observed value into the controllers, the alarm scan and the trends. A bisect from `bfed001` to `adeb18a` probed the seed 20260920 window (exporter, TIC201 last minus first, good when 2 °C or more). It names `373ba66` (2026-10-03 18:50 EDT, "every analog point carries its observed value; controllers, alarms and trends read it") as the first commit with the small rise. Both seeds read +4.2 and +4.3 at its parent `4fc55ac` and at `0dcf16d`, and +0.7 and +0.8 at `373ba66`. `0dcf16d` added the declared reporting window that the observed value passes through. Its own message says the scan and the controllers did not use the observed value yet, and that no golden moved. At `adeb18a` the window opens with TIC202 at 68.7 °C (seed 20260920) against 93.1 °C at `bfed001`. That fits `373ba66`'s own account of a faster jacket recovery, but this lane did not isolate the mechanism further.

Cross-checks, same environment:

| Manifest | Simulator | Override | Useful | Guards |
| --- | --- | --- | --- | --- |
| v2 | `bfed001` (its pin) | no | 8/8, 0 mismatches against the v2 receipts | 10/10 |
| v2 | `1f0147e` (simulator main before the S1 merge) | yes | 8/8 | 10/10 |
| v2 | `adeb18a` | yes | 6/8, both restoration-lag seeds miss only `reactor_warming` | 10/10 |
| v2 | `adeb18a` | not given | exits 2 and writes nothing | |
| v3 | `bfed001` | yes | 6/8, both restoration-lag seeds carry an unexpected `reactor_warming` | 10/10 |
| v1 | `adeb18a` | yes | 6/10 | 8/8 |

The two 6/8 rows are mirror images, so the manifest change equals the measured change.

Commands, run from the repository root against clean clones of the simulator, with Node v22.20.0 (nvm) and Python 3.14.5 on macOS 27.0:

```sh
python3 scripts/rescore_drills.py /tmp/sim-adeb18a --manifest moa/data/drills-v3.json --out receipts/drills-v3/baseline.json
python3 scripts/rescore_drills.py /tmp/sim-adeb18a --manifest moa/data/drills-v3.json --provider always-refuse --out receipts/drills-v3/always-refuse.json
python3 scripts/rescore_drills.py /tmp/sim-adeb18a --manifest moa/data/drills-v2.json --allow-revision-mismatch --out /tmp/v2-at-adeb18a.json
python3 scripts/rescore_drills.py /tmp/sim-bfed001 --manifest moa/data/drills-v2.json --compare receipts/drills-v2/baseline.json --out /tmp/v2-at-bfed001.json
python3 scripts/rescore_drills.py /tmp/sim-bfed001 --manifest moa/data/drills-v3.json --allow-revision-mismatch --out /tmp/v3-at-bfed001.json
node scripts/export_trajectory.cjs /tmp/sim-adeb18a restoration-lag 20260920 > window.json
```

Paths are shown as `/tmp`; the recorded run used throwaway clones of the same revisions in a job scratch directory. Node 22 matters: the scorer parses the exporter's stderr strictly, and Node 26 prints a warning there that breaks it. `tests/test_rescore_drills.py` reproduces both v3 receipts with 0 mismatches when `MOA_SIM_REPO` points at a clean `adeb18a` checkout, and skips otherwise.

**Scoring decision.** Changing an expectation is a scoring decision, not a measurement. Anthony's merge of the pull request that adds this manifest is what enacts it. The prior decision of this shape is drills-v2 (2026-10-03, commits `d2fdd2e` and `63654ce`, merged by Anthony in `713454f`), which moved cooling-loss to a quality abstention at `bfed001`. HQ's exposure entry for this lane is in the Sovereign Stack chronicle, domain `exposure-ledger,master-operations-agent,experion-station-sim,drills-v2,development-cases,hq-lane,2026-10-04`.

These are project-authored development expectations. They are not held-out cases, not engineer-approved ground truth, and not a model evaluation.
