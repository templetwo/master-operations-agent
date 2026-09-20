# Offline candidate diagnostics

A release score answers whether the application accepted a candidate. This diagnostic answers which authored finding and check IDs appeared in the recorded response. These are separate questions. The diagnostic never runs a model, changes policy, releases advice, or edits its source receipts.

```sh
python3 scripts/diagnose_receipts.py \
  receipts/v0.5/deepseek-live-network/cloud-model.json \
  --output receipts/my-new-diagnostic.json
```

The output must be a new file. Invalid chain links, a mismatched embedded head, duplicate JSON keys, non-finite numbers, unmatched case/run IDs, or a report result differing from its chained outcome prevent output. Every output records the input file SHA-256, diagnostic implementation SHA-256, and verified embedded head. This detects changes relative to those retained values. It provides no external authenticity guarantee or protection against whole-history replacement.

`moa.diagnostics` imports only the Python standard library. Its public entry points are `diagnose_report(report_dict)`, `diagnose_file(source_path, new_output_path)`, and `verify_bundle(bundle)`. It does not call the agent, policy, `eligible()`, release validator, or their serialization helpers. Expected findings and checks come only from explicit `case.expected` fields in the input report. These labels are outside the event chain, so the file hash and separate expectation hash document the exact labels used. They remain authored development expectations, not independently established process truth.

Each case is linked to its terminal outcome and last parsed provider response by `run_id`. When a later provider call has no parsed response, an earlier answer is not reused. Input guards without provider responses, abstentions, unfinished tool sequences, invalid response shapes, and absent candidates remain visible. Raw invalid provider text is not recovered or guessed into JSON.

Each case has two views:

- `original`: envelope assessment and finding/check ID comparison using the exact recorded response.
- `offline_packaging_diagnostic`: the same comparisons after explicitly recorded removal of an extra `type: "json_object"` field or inspection of the observed `{ "type": "json_object", "content": {...} }` wrapper. No other fields or IDs are repaired. Unknown wrappers and extra wrapper fields are not normalized.

An envelope assessment only describes response shape. A valid tool or abstention envelope is not useful advice. A valid advice envelope still says nothing about evidence provenance, required reads, freshness, valid process interpretation, or release eligibility. Those decisions are preserved in the original release status and reason.

The advisory summary denominator includes every authored case with expected status `advisory`, even when a candidate is absent, abstains, or is malformed. Expected guard cases are retained per case but excluded from advisory content aggregates. Per-field counts retain expected, predicted, matched, omitted, and extra IDs:

- Micro recall is total matched IDs divided by total expected IDs.
- Micro precision is total matched IDs divided by total predicted unique IDs.
- A zero denominator produces `null`, never a perfect score.
- Absent or invalid ID lists contribute zero matched and predicted IDs, with all expected IDs counted as omissions. The `prediction_observed` flag distinguishes absent predictions from observed empty lists.
- Duplicate IDs are compared as sets for overlap but make the list invalid. Empty, duplicate, absent, and malformed lists cannot earn an exact-set result.

Finding/check overlap is a description of content relative to the supplied labels. It does not grade severity or verify evidence references and must not be presented as a safety or capability score. Catalog IDs that overlap can still accompany unsupported or invalid content.

Historical results are in [the v0.6 diagnostic receipt index](../receipts/v0.6/diagnostics/README.md). DeepSeek's offline packaging view contains every expected finding and check, but includes extra findings in five cases and extra checks in all ten. The latest local 9B report misses required content. Both retain their original 0/10 release usefulness. No new model inference was used for these observations.

Tests include independent authored chain fixtures, tampering, result/event mismatches, malformed JSON, wrapper preservation, duplicate and empty IDs, undefined metric denominators, abstention controls, and an actual subprocess invocation of the CLI. Historical model, baseline, and always-refuse receipts are additional regression examples. They test the reader and accounting, not the correctness of the authored process labels.
