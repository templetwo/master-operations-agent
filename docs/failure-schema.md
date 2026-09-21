# Failure accounting contract

New abstention outcomes include `failure` with three strings: `stage`, `category` and `code`. `reason` retains the existing rejection code. The extra metadata describes where the attempt stopped; it does not change validation or authorize a release.

```json
{"stage":"candidate_validation","category":"candidate_shape","code":"schema"}
```

| Stage or condition | Category | Interpretation |
|---|---|---|
| `input_validation` | `input_validation` | Input rejected before provider use |
| `freshness_validation`, or stale/future at `tool_execution` | `input_freshness` | Evidence no longer usable |
| `provider_prepare` | `provider_preparation` | Provider setup did not complete |
| `provider_response` | `provider_response` | Provider transport, identity, parsing or response failure |
| `tool_request`, other `tool_execution` | `tool_protocol` | Invalid or unavailable read operation |
| `model_abstained` code | `model_abstention` | Model explicitly abstained |
| `candidate_validation` with unsupported finding, check, evidence or `ungrounded` | `candidate_content` | Content or evidence requirement failed |
| Other envelope/candidate failures | `candidate_shape` | Final or response shape invalid |
| `tool_budget` or `provider_budget`, at any stage | `budget` | Hard call/turn limit reached; takes precedence |

In particular, `schema` at `candidate_validation` counts as a candidate rejection. The same code at an input or tool boundary does not. A provider JSON parse failure does not prove a final candidate was received. Historical outcomes without `failure` stay unclassified rather than receiving guessed stages.

Report useful task completion and input guards separately. A legitimate guard can pass its expected guard case; the same abstention does not complete a usable case. Candidate rejection counts include `candidate_shape` and `candidate_content`, including response-envelope failures. They exclude input, provider, tool-protocol, budget and explicit model-abstention categories, so they are not a total task-failure rate. Read completion means the requested results were delivered, not understood. See [offline diagnostics](diagnostics.md) for expected-ID overlap and its limits.
