# Source-map v2 evaluation

Recorded 2026-09-27 by the MacBook seat (grok-4.6) on `Anthonys-MacBook-Pro.local`.

This is a new run. It does not replace the development denominator or the v0.8 slice.

| Binding | Revision |
| --- | --- |
| Simulator main | `bfed001fc89d9beaa640b30a7886d5f16f61a31b` (merge of PR #2) |
| Model id | `670f49e40c2b3395735e85b3bd09205f77f4a0598c955959f061f1d18810c832` |
| MOA main at scoring | `ac2524372204bb4ead7a3b7dedb00953b101fe5b` (merge of PR #1) |
| Provider | deterministic baseline. Models called: 0 |

The historical case list in `moa/data/drills-v1.json` was applied unchanged. That file is still pinned to simulator `3aad7695b8720b291999ef0903fcab7b7e008f1e`, sha256 `4da8c8d0a2875a6b706798834af46ceece68a381e2401689f40b279b23885b62`. The standing 10/10 useful and 8/8 guard score belongs to that pin. It was not re-run and not edited.

This run, against `bfed001`: **8/10 useful, 8/8 guards**. Both `cooling-loss` seeds abstain with reason `quality`. TIC202 is 103.125 °C, quality `uncertain`. The other advisory cases still match the historical findings. Guard cases, including `bad-quality` and the six boundary perturbations, still abstain for the expected reasons.

`moa/data/stream-v1.json` is still `edd9dbc` / model `cc0b2a83…`, sha256 `e15e554184dba3bcd7e626d63b039343aaa7b84fd309965be237c0a283df035b`. `run_slice` was not called. `receipts/current.json` was not moved. No campaign receipt was rewritten.

Full rows: [evaluation.json](evaluation.json), sha256 `ea62fdf50b0c66f0431b95dc4f3744054b8ef80f6218c373c0978c66223b7a19`.
