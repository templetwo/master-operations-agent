# Four-arm guidance experiment

This is a controlled development diagnostic, not model promotion or held-out evaluation. The original release policy, validator, default prompt, provider settings, and historical receipts remain unchanged. Two static guidance additions are varied: exact output-contract instructions and the complete existing policy mapping.

| Arm | Output guidance | Policy guidance |
|---|---|---|
| unchanged | No | No |
| output-only | Yes | No |
| policy-only | No | Yes |
| both | Yes | Yes |

Each arm receives ten usable and eight invalid-input cases from the existing pinned simulator development suite. Four independent case generators produce matching process data with fresh capture times. Arm order rotates by case index to reduce fixed-order confounding. Every model assessment has its own context; no answer is carried between arms or cases. Provider caching, mutable deployment identity, and time effects remain limitations.

The code first writes a preregistration containing complete prompts, hashes, fixed endpoints/settings, denominators, primary/secondary outcomes, call bounds, and stopping rules. An execution requires its exact SHA256 and unchanged source hashes. Commit the preregistration before inference. A change requires a new registration and must be reported as a new experiment, never a replacement for an inconvenient outcome.

```sh
python3 -m moa register-guidance-experiment --output receipts/new-registration.json
python3 -m moa guidance-experiment \
  --sim-repo /path/to/trusted/experion-station-sim \
  --env-file /path/outside/repo/.env \
  --preregistration receipts/new-registration.json \
  --expected-sha256 HASH_PRINTED_BY_REGISTRATION \
  --allow-cloud-synthetic --output receipts/new-experiment
```

The command permits at most 244 completion requests across four providers: one warmup and at most six responses for each of ten usable cases per arm. Input guards should make no inference calls. Baseline and always-refuse controls run first. Setup, transport, authentication, or model-identity failures interrupt the run; partial progress and full event exports remain available. Delivered malformed or truncated output from the confirmed alias counts as a failed scored case and the experiment continues. No retry, alternate model, credential logging, observation-file upload, or plant path is introduced.

Primary outcome is accepted useful advisories out of ten for each arm, with paired differences from the unchanged arm. Secondary outcomes include failure stage, completed reads, original and offline diagnostic content coverage/extras, elapsed time, and token usage. Format-normalized diagnostic content never bypasses the release validator. Precise provider-request bytes remain hashed. Raw outputs and inputs remain in the event chain.

A valid completed experiment returns exit 0 even if every model arm fails usefulness. Exit 1 means integrity checks failed; exit 2 means execution was interrupted or rejected. This differs from `compare-deepseek`, whose exit 1 can mean an otherwise valid negative model result. Consult the JSON result rather than interpreting shell success as model success.

This one-pass development comparison can show an observed difference in these configurations. It cannot establish a stable causal effect, statistical efficacy, generalization, or plant safety. No prompt is silently promoted after inspecting results. Independent holdout preparation is a separate stage.
