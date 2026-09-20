# V0.5: explicit DeepSeek integration, authentication blocked

Recorded 2026-09-20. The user explicitly requested testing DeepSeek-V4.1-Flash with an existing project credential. Two distinct literal `DEEPSEEK_API_KEY` values were located in project dotenv files. Each was tested once against the fixed official model-list endpoint and rejected with HTTP 401:

- [First credential attempt](deepseek-access.json).
- [Distinct alternate credential attempt](deepseek-access-alternate.json).

No credential value, authorization header, dotenv content, or remote error body was recorded. No key was copied into this repository. The authentication attempts sent no simulator observations or model prompts. No completion was requested, and there is no DeepSeek answer-quality score.

The new `compare-deepseek` command is explicit, synthetic-only, bounded, and retains the existing policy and independent validator. It requires a user-selected credential file and a working credential before proceeding. See [setup and source receipts](../../docs/deepseek.md).

[Validation](validation/validation.json): 75 tests passed, including simulator integration and the mocked cloud comparison. The public smoke suite, baseline drill scorecard, and JavaScript syntax checks passed. DeepSeek transport and positive end-to-end comparison tests use fake credentials and a mocked model; the latter runs real headless simulator exports. They establish implementation behavior, not cloud model capability. The original deterministic and local-model receipts remain separate.

[Credential exposure check](credential-check.json) compared both attempted keys in memory against tracked and unignored repository files. Neither key was found. Values and credential hashes were not retained.
