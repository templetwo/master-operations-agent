# DeepSeek synthetic comparison

The explicit `compare-deepseek` command sends generated simulator observations and the research policy to the official DeepSeek API. It does not change the baseline default, enable cloud access in the dashboard, or accept imported observation files. The user must choose a trusted simulator checkout, a credential file, a new output directory, and the cloud flag.

```sh
python3 -m moa compare-deepseek \
  --sim-repo /path/to/experion-station-sim \
  --env-file /path/to/project/.env \
  --allow-cloud-synthetic \
  --output receipts/new-deepseek-comparison
```

The loader reads one literal `DEEPSEEK_API_KEY` assignment from the named file. It supports optional `export`, matching single or double quotes, and trailing comments. It does not source a shell, expand variables, discover keys automatically, copy the dotenv file, or record the credential. Duplicate, missing, nonliteral, or malformed assignments fail before network access. Keep the real key in the existing ignored credential file, never in a command argument or repository receipt.

The client uses certificate-validated HTTPS to the fixed `api.deepseek.com` host. Only `/models` and `/chat/completions` are available to the client. It ignores proxy variables and custom base URLs, does not follow redirects, does not retry, and has no alternate-model fallback. Remote error bodies are discarded. A response that echoes the credential is discarded before recording content. Requests containing the credential are rejected before transmission.

## Model and protocol

As read on 2026-09-20, DeepSeek's official model table maps `deepseek-flash` to DeepSeek-V4.1-Flash. This is a mutable service alias, not an immutable artifact pin. The client requires that exact alias in the authenticated model listing and records the returned model name, response ID, available system fingerprint, and usage. It does not claim that a stable alias proves unchanged weights. [Official model table](https://api-docs.deepseek.com/quick_start/pricing/), read 2026-09-20.

The first configuration requests non-thinking mode, temperature 0, maximum 768 output tokens, and non-streaming JSON output. This keeps the output budget and thinking choice comparable to the local experiments. DeepSeek uses `response_format: {"type":"json_object"}`; the local Ollama provider uses a union JSON schema. These are different decoding constraints. Both feed the same independently validated candidate format, read-only tools, policy, six-turn limit, and 60-second freshness gate. [Chat API](https://api-docs.deepseek.com/api/create-chat-completion/) and [JSON output guide](https://api-docs.deepseek.com/guides/json_mode/), read 2026-09-20.

No native DeepSeek tool execution, file upload, reasoning trace storage, streaming, or live plant data path is added. The model proposes a JSON read request and the existing reference boundary performs only allowed reads. Synthetic labels alone are not authentication; this command uses the existing pinned headless simulator exporter, not a user-imported projection that merely claims to be synthetic.

## Receipts and limits

The runner checks model availability and makes one synthetic protocol request before scored inference. It then runs the same deterministic baseline, always-refuse control, and generated development cases as the local comparator. Baseline expectations and process-data pairing must pass. Source hashes, original observations, tool reads, candidates, rejections, request hashes, available usage, and wall time are retained. Failed setup is marked interrupted, never scored as a model-quality result.

The client allows at most 61 inference requests per comparison, including the initial protocol request. Each request is bounded in size, output tokens, and socket timeout. Unknown usage counters remain unknown. Warmup usage is in `warmup.json`; scored usage is separate. The tool does not report an estimated cost as an actual charge. Consult the provider account for billed amounts.

Exit 0 means the cloud run met this development scorecard and comparison checks. Exit 1 means it completed without meeting them. Exit 2 means setup or execution failed. No result is an independent holdout score, controls review, or authorization for plant use.

## Current status

The updated credential authenticated successfully on 2026-09-20. The actual comparison completed with 40 scored inference calls and one warmup. DeepSeek completed required reads on all 10 usable cases but produced no accepted advisory: nine candidates failed the JSON contract and one failed finding validation. All eight invalid inputs were blocked before inference by application guards. Comparison integrity and all three evidence-chain checks passed. See [actual results and limitations](../receipts/v0.5/deepseek-live-network/README.md). The earlier HTTP 401 receipts remain historical records, separate from this completed run.
