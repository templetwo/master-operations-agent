# Implementation provenance

Anthony Vasquez directed this project. Implementation and research preparation in this conversation were performed with OpenAI Codex and delegated Codex agents. Existing Git author fields identify the account used to commit; they do not independently identify who wrote every line. This record is additive and does not rewrite historical commit identities.

The v0.6 implementation and experiment preparation were published at `44545fd3857547af519da24fc5a03d16392b9f64`; aggregate results, review capsules and completion documentation at `edb41bf6ce15285d1c437089d22cdef5c5b50cbb`. Codex agents handled accounting, policy review, private holdout authoring and private review. The author saw eligibility implementation; the reviewer had development-code exposure. Neither was a controls engineer or an independent external attestor.

For v0.7, the coordinating Codex role remains unexposed to holdout observations, labels and per-case diagnostics. The previously exposed holdout reviewer prepares the evaluation runner without changing the candidate. A separate evaluator executes the frozen campaign after preregistration publication. Public reporting contains aggregates only. Exposure and execution status are recorded in the campaign receipts, not inferred from this plan.

User-supplied Claude Code and Kimi reviews inform the work. Their statements are reviewer reports; this repository does not turn those statements into independent proof of API traffic or industrial readiness. Hash chains and source hashes support retained-record consistency. They are not external attestation.

This repository-local provenance entry is not a claim that the separate Sovereign Stack chronicle was updated.
