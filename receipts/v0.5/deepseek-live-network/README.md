# DeepSeek actual synthetic development run

Recorded 2026-09-20 after the user updated the project credential. Authenticated model listing and inference succeeded against the official API. The requested and returned alias was `deepseek-flash`, documented as DeepSeek-V4.1-Flash in the [official model table](https://api-docs.deepseek.com/quick_start/pricing/), read 2026-09-20. A mutable alias does not identify immutable weights.

[Comparison](comparison.json), [run configuration](run.json), [full cloud evidence](cloud-model.json), and [independent receipt audit](audit.json).

| Measurement | Result |
|---|---|
| Comparison integrity | Passed: identical paired process data, unchanged source, alias still listed |
| Deterministic baseline usefulness | 10/10 |
| Always-refuse control usefulness | 0/10 |
| DeepSeek completed required evidence reads | 10/10 usable cases |
| DeepSeek accepted useful advisories | 0/10 |
| Application input guards | 8/8, blocked before model inference |
| Usable candidate outcomes | 8 unexpected-field schema failures, 1 unknown-kind schema failure, 1 unsupported/missing finding failure |
| Usable-case end-to-end latency | Median 4.317 seconds; maximum 4.908 seconds |
| Actual inference calls | 40 scored calls plus 1 unscored protocol warmup |
| Scored reported tokens | 71,320 input; 1,655 output; 72,975 total |

The responses generally added `type: json_object` to the final candidate. One wrapped the candidate inside a `content` object. Those violate the existing exact contract. The schema-valid response failed the finding validator. The client neither removed fields nor repaired or released rejected advice. These outcomes do not establish that fixing JSON shape alone would make the content correct.

The original `candidate_rejections` aggregate is 2 because its existing category list omits generic `schema` outcomes. The case records and audit show all 10 usable candidates rejected. Original reports remain unchanged. The eight input guards are application behavior, not voluntary model abstention; no model call was made for those cases.

The manifest, policy, system prompt, and entry message hashes match the v0.4 local read-state comparison. Both DeepSeek and that local run scored 0/10 usefulness. DeepSeek used JSON mode while Ollama used schema-constrained decoding, so this is a comparison of tested configurations, not a general model ranking. Non-streaming requests do not measure time to first token. Reported usage excludes the separately recorded [warmup](warmup.json); no actual bill is inferred.

All three exported evidence chains were recomputed and checked against their SQLite stores. These local anchors are integrity checks, not external attestation. [Credential exposure audit](credential-check.json) scans the updated key in memory without recording its value or hash.

No runtime or policy changes were made for this evaluation. The existing 75-test implementation validation remains applicable. These project-authored development drills are not held-out evaluation or controls-engineer review. No provider promotion or plant connection follows from this run.
