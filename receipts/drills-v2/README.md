# Development drills v2 at simulator bfed001

Recorded 2026-10-03 by the MacBook seat (claude-opus-5-5) on `Anthonys-MacBook-Pro.local`. Deterministic providers only. Models called: 0.

[`moa/data/drills-v2.json`](../../moa/data/drills-v2.json) (sha256 `165e12c7cdd238d10f590c174b29747c7302a06a33692fa537be7e2f38163438`) is a new development manifest pinned to simulator `bfed001fc89d9beaa640b30a7886d5f16f61a31b`. It is derived from `drills-v1.json` (sha256 `4da8c8d0…`, pinned to `3aad769`), which is unchanged and remains the pin for every existing experiment module.

One expectation changed. At `bfed001` the cooling-loss scenario drives TIC202 above its declared 0 to 100 °C range, the simulator reports it uncertain at 103.125, and the advice gate withholds advice for a non-good current tag. v2 expects that quality abstention for both cooling-loss seeds instead of the v1 advisory. Every other case is byte-identical. The [source-map v2 evaluation](../source-map-v2/README.md) recorded the same behaviour against the v1 expectations.

| Run | Useful assessment | Input guards | Voluntary abstentions | Receipt |
| --- | --- | --- | --- | --- |
| Deterministic baseline | 8/8 | 10/10 | 0 | [baseline.json](baseline.json), sha256 `64f5a0974c43cb9e1c084483c55dbf78272a18c02346b6d9523d36340fc3d2b3` |
| Always-refuse negative control | 0/8 | 10/10 | 8 | [always-refuse.json](always-refuse.json), sha256 `1906fa36d972eae7f1a10e503e991c0fbb85238f46bb539ac7d0a91a9a5d3283` |

The useful denominator falls from 10 to 8 because both cooling-loss seeds are now guard cases. This scorecard no longer measures a supported cooling-loss assessment. Whether a cooling-loss window can be exported before the jacket reaches the range limit, with enough fault evidence to assess, is an open question for a later manifest.

Commands, run from the repository root against a clean clone at `bfed001`, with Node v22.23.2 and Python 3.10.12:

```sh
python3 scripts/rescore_drills.py /tmp/sim-bfed001 --manifest moa/data/drills-v2.json --out receipts/drills-v2/baseline.json
python3 scripts/rescore_drills.py /tmp/sim-bfed001 --manifest moa/data/drills-v2.json --provider always-refuse --out receipts/drills-v2/always-refuse.json
```

Paths are shown as `/tmp`; the recorded run used throwaway clones of the same revision in a job scratch directory.

These are project-authored development expectations. They are not held-out cases, not engineer-approved ground truth, and not a model evaluation.
