# Gemma public backend compatibility probe

On 2026-09-21 UTC, `gemma4:12b-mlx` failed a public schema-enforcement probe on Ollama 0.32.6. A matched `qwen3:4b` GGUF control passed. Neither run opened the private holdout or ran an operations case. No model was promoted, downloaded, or sent a cloud request.

| Installed model | Schema result | Returned content | Completion calls |
|---|---|---|---|
| Gemma 4 12B MLX | Failed | `{"probe":"user_requested_wrong","extra":true}` | 1 |
| Qwen3 4B GGUF | Passed | `{"probe":"schema_only_7c92"}` | 1 |

The prompt asks for a deliberately forbidden value and extra field. The API's `format` schema permits only `{"probe":"schema_only_7c92"}`. The two request objects are identical except for the model name. Both returned HTTP 200 and reported completed generation. This tests enforcement of the supplied schema, not willingness to follow a schema described in a prompt.

Both used temperature 0, seed 0, 768 output tokens, `think:false`, and requested 8,192 context tokens. The daemon reported 8,192 loaded context tokens for each; that report is not independent proof of context enforcement. Model metadata and source hashes were unchanged during each run. The runs happened separately, at 03:52 and 07:40 UTC, so this is not a simultaneous controlled comparison. Different model families also prevent isolating backend as the sole cause.

## Receipts and reproduction

- [Gemma run](backend-probe/run.json), [schema result](backend-probe/schema.json), [exact request](backend-probe/schema.request.json), and [raw response](backend-probe/schema.response.txt).
- [Qwen control run](gguf-control-network/run.json), [schema result](gguf-control-network/schema.json), [exact request](gguf-control-network/schema.request.json), and [raw response](gguf-control-network/schema.response.txt).
- [Probe implementation](../../scripts/probe_backend.py). The [original implementation snapshot](backend-probe/probe_backend.py.txt) preserves the script hash recorded by the Gemma run. The only subsequent behavior addition was `--schema-only`, used to prevent the successful Qwen control from launching a public operations window.

The probe records its plan before inference locally. It was not publicly preregistered before inference and is a diagnostic, not a frozen accuracy study. Hashes and local records are not external attestation of inference.

```sh
python3 scripts/probe_backend.py --model gemma4:12b-mlx --expected-digest ded7a27350032202d9e9b2a6071e8aa89959ab156771b5228f30863c741c4970 --schema-only --output /tmp/moa-gemma-new-probe
python3 scripts/probe_backend.py --model qwen3:4b --expected-digest 359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7 --schema-only --output /tmp/moa-qwen-new-probe
```

These commands require the exact models already installed and fresh output paths. A failed schema probe exits 1. Without `--schema-only`, a passing probe can make up to six additional calls on one public fixture. The recorded Gemma failure made no such calls.

Two control preparations preceded the successful control: an invalid digest argument failed before provider construction, and a sandbox-blocked preparation failed before a completion request. The latter's [interrupted record](gguf-control-run/run.json) is retained. Neither was a model response or a retry of a scored case. The invalid argument created only an empty output directory, with no receipt file.

## Interpretation and next gate

The tested Gemma configuration does not satisfy the structured-output compatibility gate. The Qwen control shows that this same public schema can be enforced through this daemon with another installed model. This is consistent with upstream MLX reports, but it does not prove an implementation-level root cause or that every MLX version fails. It gives no Gemma operations usefulness score.

Before a Gemma accuracy campaign, verify a compatible serving configuration with public schema probes, pin its model and provider settings, and register a separate evaluation. A GGUF Gemma build is a candidate to investigate, not a verified fix. Existing validators, prompts, holdout files and historical campaigns remain unchanged.

## Sources read 2026-09-21

Publication checks: 122 tests passed with `MOA_SIM_REPO=/Users/vaquez/experion-station-sim python3 -m unittest discover -s tests -v`. Exact request/response hashes and both probe script hashes matched their records. The 12 probe files scanned showed no matches for the credential patterns checked; this is not a comprehensive secret-detection guarantee. `git diff --cached --check` passed.

- [Ollama structured-output documentation](https://github.com/ollama/ollama/blob/main/docs/capabilities/structured-outputs.mdx): documents passing a JSON schema through `format`.
- [Ollama issue 17183](https://github.com/ollama/ollama/issues/17183): reporter describes schema non-enforcement on `gemma4:12b-mlx` and other MLX models, with GGUF comparisons. This is a user report in the upstream tracker, not vendor certification.
- [Ollama issue 17933](https://github.com/ollama/ollama/issues/17933): another reporter describes silent MLX structured-output failure; closed as a duplicate. We have not verified that report's implementation diagnosis.

## GGUF follow-up, 2026-09-21

After the user said to proceed, the official `gemma4:12b-it-q4_K_M` build was downloaded alongside MLX. Ollama verified its digest and completed installation. Installed size is 7,556,508,396 bytes, artifact digest `4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c`, reported format GGUF and quantization Q4_K_M. The [official tag list](https://ollama.com/library/gemma4/tags), read 2026-09-21, identifies this build. Representation and quantization differ from the MLX build; this is not a backend-only ablation.

The [GGUF run](gguf-probe/run.json) used the same schema-conflict prompt and settings. It [passed schema enforcement](gguf-probe/schema.json), returning the sole permitted object. The daemon reported 8,192 loaded context tokens. The subsequent [public operations window](gguf-probe/public-window.json) completed three required reads and a final candidate in four calls, but the unchanged validator withheld it with `unsupported_finding`. Its whole-assessment elapsed time was 35.002 seconds, not time to first token. Total diagnostic inference was five calls: one schema probe plus four public-window calls.

Source and metadata remained unchanged during the probe, executed from commit `d4cb159`. This resolves the observed schema gate for this GGUF configuration, not operations usefulness. The separate [Gemma campaign protocol](../../docs/gemma-holdout-v0.7.md) preserves that failed public example and fixes evaluation settings before private execution.
