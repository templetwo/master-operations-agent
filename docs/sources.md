# Implementation source receipts

Read date: **2026-09-20 UTC**. Project design decisions and authored demo thresholds are labeled as such in the architecture. This table supports the narrow interfaces used in v0.1, not the broader model/pricing claims in the initial roadmap.

| Source URL | What was read and used | Read date | Limit |
|---|---|---|---|
| https://docs.ollama.com/api/chat | `/api/chat`, model/messages, structured `format`, streaming flag, completion fields | 2026-09-20 | Interface documentation; not a model-quality result |
| https://docs.ollama.com/capabilities/structured-outputs | JSON schema passed through `format`, client-side validation still used | 2026-09-20 | Schema constraints do not establish process correctness |
| https://docs.ollama.com/api/tags | Installed-model listing, name and digest fields | 2026-09-20 | Daemon-reported metadata |
| https://github.com/ollama/ollama/blob/main/docs/api.md | `/api/show` metadata endpoint | 2026-09-20 | Moving branch; actual provider transport verified with mocks |
| https://github.com/ollama/ollama/blob/main/docs/openapi.yaml | Remote model and host metadata in model summaries | 2026-09-20 | Client checks do not enforce daemon network isolation |
| https://docs.ollama.com/faq | Local daemon deployment context | 2026-09-20 | Read, not an audit of the user's daemon configuration |
| https://github.com/templetwo/experion-station-sim/blob/3aad7695b8720b291999ef0903fcab7b7e008f1e/Experion%20Station%20Simulator.dc.html | Local checkout read: `coachProjection`, operator catalog, bounded alarm list, exact tag units | 2026-09-20 | Projection completeness is checked by the exporter; no hidden-state assessment claim |
| https://github.com/templetwo/experion-station-sim/blob/3aad7695b8720b291999ef0903fcab7b7e008f1e/tools/logic-harness.js | Local checkout read: headless Component loader | 2026-09-20 | Trusted operator-run code, not an agent capability |
| https://github.com/templetwo/experion-station-sim/blob/3aad7695b8720b291999ef0903fcab7b7e008f1e/tests/coach-projection.test.js | Local checkout read: operator-visible projection and hidden-fault exclusions | 2026-09-20 | Our adapter was also tested on normal and bad-quality exports |

The time-series extension's pinned simulator sources, generation protocol, and measured-result limits are recorded in [drills.md](drills.md). Its expectations are project-authored, with independent controls review pending.

The earlier claim-by-claim research audit remains at the sibling local directory `../master-operations-agent-research/2026-09-20/`. It is background research, not a dependency or a claim that this project completed every roadmap stage. The direct web URL `https://docs.ollama.com/api/show` was not retrievable during this build; the official GitHub API documentation was used instead.
