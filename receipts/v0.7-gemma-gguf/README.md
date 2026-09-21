# Gemma GGUF registered comparison

This directory holds the single-candidate Gemma extension on the existing private synthetic u1-v1 corpus. The [protocol](../../docs/gemma-holdout-v0.7.md) fixes the original policy-only prompt, validator, 24 usable cases, six guards, controls and failure accounting. [Inventory](inventory.json) pins the downloaded model digest and provider metadata.

The [public compatibility probe](../v0.7-gemma/gguf-probe/run.json) passed schema enforcement but produced a withheld operations candidate. That probe is not a held-out accuracy result. Registration and an aggregate will be published separately as execution proceeds. No model promotion is authorized.
