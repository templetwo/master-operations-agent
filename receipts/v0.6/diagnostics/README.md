# Historical offline diagnostics

24 historical model/control reports analyzed with `moa.diagnostics`. No model calls, original receipt changes, or release rescoring. The input file SHA-256 and verified embedded head are retained in each output. The input authored expectations are not independently reviewed truth.

Reproduce each indexed row with:

```sh
python3 scripts/diagnose_receipts.py INPUT --output NEW_OUTPUT.json
```

The table reports content sets after the explicitly recorded, offline-only packaging inspection. It does not indicate accepted advice. Every model report originally scored 0/10 usefulness.

| Source | Exact findings | Exact checks | Finding recall | Check recall |
|---|---:|---:|---:|---:|
| [receipts/v0.3/qwen3-4b-entry-v3/local-model.json](v0.3__qwen3-4b-entry-v3__local-model.json) | 0/10 | 0/10 | 0.000 | 0.000 |
| [receipts/v0.3/qwen3-4b-local/local-model.json](v0.3__qwen3-4b-local__local-model.json) | 0/10 | 0/10 | 0.000 | 0.000 |
| [receipts/v0.3/qwen3-4b-protocol-v2/local-model.json](v0.3__qwen3-4b-protocol-v2__local-model.json) | 0/10 | 0/10 | 0.000 | 0.000 |
| [receipts/v0.3/qwen35-9b-entry-v3/local-model.json](v0.3__qwen35-9b-entry-v3__local-model.json) | 0/10 | 0/10 | 0.000 | 0.000 |
| [receipts/v0.4/qwen3-4b/local-model.json](v0.4__qwen3-4b__local-model.json) | 0/10 | 0/10 | 0.650 | 0.885 |
| [receipts/v0.4/qwen35-9b/local-model.json](v0.4__qwen35-9b__local-model.json) | 0/10 | 0/10 | 0.050 | 0.000 |
| [receipts/v0.4/qwen35-9b-read-state/local-model.json](v0.4__qwen35-9b-read-state__local-model.json) | 0/10 | 0/10 | 0.300 | 0.077 |
| [receipts/v0.5/deepseek-live-network/cloud-model.json](v0.5__deepseek-live-network__cloud-model.json) | 5/10 | 0/10 | 1.000 | 1.000 |

All baseline and always-refuse controls are also included in [index.json](index.json). Baselines have 10/10 exact finding/check sets; always-refuse controls have 0/10. This demonstrates diagnostic discrimination on these authored cases, not independent policy correctness.
