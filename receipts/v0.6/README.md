# Five-stage remediation receipts

Requested 2026-09-20. [Execution plan](../../docs/v0.6-plan.md). Original v0.3, v0.4, and v0.5 reports are unchanged. The application remains advisory-only, with its original release validator and deterministic default.

| Stage | Delivered evidence |
|---|---|
| 1. Failure accounting | New terminal stage/category/code metadata, reconciled useful/guard cohorts, and candidate counts separated from input/provider/tool failures. [Tests](../../tests/test_accounting.py) and [actual-run reconciliation](guidance-live/audit.json). Historical missing stage metadata stays unclassified. |
| 2. Offline diagnostics | Independent stdlib reader verifies full chains and outcome bindings; compares findings/checks with explicit labels. [24 historical reports](diagnostics/README.md), [implementation](../../moa/diagnostics.py), and [contract](../../docs/diagnostics.md). No source receipt or release outcome changed. |
| 3. Complete policy mapping | [Static optional guidance](../../moa/guidance.py), [mapping and limits](../../docs/policy-contract.md), and independently authored example tests. Existing policy hash and validator unchanged. |
| 4. Controlled experiment | [Preregistration](guidance-preregistration.json), [peer review](experiment-peer-review.json), [actual four-arm outcomes](guidance-live/README.md), and complete event exports/diagnostics. |
| 5. Frozen holdout | [Protocol](../../docs/holdout-protocol.md), [author capsule](holdout-author.json), and [separate-agent review/freeze](holdout-review.json). All 30 authored expectations reviewed, materializer metadata corrected, final hashes frozen. No model evaluation or capability claim is made. |

The [full validation](validation-final/validation.json) passed 103 tests, including real simulator exports, local HTTP boundaries, mocked cloud transport/factorial integration, and offline reader tests. Public baseline smoke, all 18 baseline drills, and three JavaScript syntax checks passed. These establish implementation behavior, not model competence.

The public [Research checks CI run](https://github.com/templetwo/master-operations-agent/actions/runs/35517399636) for implementation/preregistration commit `44545fd` succeeded. Its workflow runs unit discovery and baseline smoke across Python 3.10, 3.12, and 3.14; optional simulator integration is covered by the separate full local validation above.

The actual cloud experiment made 160 scored completion calls and four warmups. It was preregistered and published in commit `44545fd` before inference. The unchanged and output-only arms accepted 0/10 usable cases, policy-only accepted 5/10, and both accepted 4/10. Every arm completed all required reads, and every guard case was blocked before model inference. Policy guidance reduced excess check selection in this run; unsupported finding selection remains. This is one small, reused development set with mutable cloud inference, not held-out efficacy evidence.

Agent roles were separated: accounting implementation, offline diagnostics implementation, policy specification, coordinating experiment implementation, private holdout author, and a different private holdout reviewer. Internal peer review caught an experiment stopping-rule problem before preregistration and a holdout metadata-isolation issue before final freezing. These are agent reviews, not independent controls-engineer approval. Author/reviewer exposure is disclosed in their receipts.

The private holdout contains 24 usable contract/policy windows and six guard cases. The reviewer independently recomputed all expected sets without production eligibility or model calls and verified the corrected materializer. An exact normalized-content overlap check found no matches against the archived development inputs; that does not establish new process regimes or physical realism. The coordinating/tuning role did not receive holdout observations, labels, or per-case results. Future evaluation criteria and exposure rules are frozen in the holdout protocol before any model run. Detailed corpus/review material remains outside Git; only aggregate methods, limitations, and hashes are public.

All five requested stages are complete within the declared synthetic research scope. Remaining gates include independent controls-engineer review, a separately authorized/frozen candidate holdout evaluation, and demonstration of value beyond the deterministic baseline. The measured development improvements do not grant plant authority or justify default-provider promotion.
