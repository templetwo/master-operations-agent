# Build sequence

Status recorded 2026-09-20. This repository starts the independent research lane. No stage here grants plant authority.

## 0. Working advisory foundation

Implemented: local workbench, strict synthetic contracts, finite tool loop, independent candidate validator, deterministic baseline, local evidence, simulator export, optional local-model protocol, and adversarial regression tests. The public smoke suite checks useful assessment and input guards separately. Supported and stale dashboard flows were checked in Comet. V0.3 adds actual local-model development comparisons with preserved failure receipts.

This is part of the original Stage 0, not completion of it. The original Ignition-plus-peb end-to-end gate remains open.

## 1. Evidence of useful operations reasoning

Implemented in v0.2: a versioned time-series projection with units, quality, simulation clock, contiguous within-window sequence, endpoint binding, and explicit coverage. The development scorecard covers cooling loss, feed disturbance, bad instrumentation, contradictory/missing history, restoration lag, and falling-temperature recovery windows. Operator-visible data is separated from evaluator labels. This is not authenticated sequence enforcement across successive live reads.

Have a controls engineer review expected findings, missing-evidence requests, and permitted advisory wording. Freeze held-out drills before model selection. Report per-scenario usefulness, unsafe advice, evidence fidelity, freshness failures, voluntary abstention, boundary denials, and latency. Report denominators and uncertainty; do not collapse them into one headline accuracy.

Gate: useful performance exceeds an always-refuse and a simple rule baseline without hiding unsafe recommendations in an average. Thresholds and sample sizes must be fixed before seeing results. Public smoke cases cannot satisfy this gate.

## 2. Select and improve the local model

Implemented in v0.3: installed-artifact digest pins, quantization and template metadata, fixed requested settings, hardware and serving-version receipts, separate warmup, per-call counters, paired simulator data, and baseline/refusal controls. Actual results are in `receipts/v0.3/`. These are development diagnostics; no model is promoted. Controlled cold/warm experiments, time to first token, and independent verification of daemon isolation remain open.

V0.4 fixes an order-sensitive schema serialization defect found through an order-only experiment. It preserves schema field order on the wire, receipts exact byte hashes, and explicitly reports remaining required reads after tool results. The policy, independent validator, and development expectations are unchanged. Corrected runs are in `receipts/v0.4/`. Protocol compliance and useful process assessment remain separate measures.

V0.5 adds the user-requested DeepSeek-V4.1-Flash synthetic comparison through the documented `deepseek-flash` API alias. Transport and simulator-runner tests pass with mocks. After the credential update, actual API inference completed: all required reads succeeded on 10/10 usable cases, but usefulness was 0/10. Nine candidates failed the exact JSON contract and one failed finding validation. The eight input guards blocked cases before inference. [Receipts](../receipts/v0.5/deepseek-live-network/README.md) preserve this negative result. Next work should test explicit output-contract guidance and policy application as separate development changes while keeping the validator fixed.

Improve retrieval and evidence selection first. Consider SFT or preference training only after baseline failures identify a learnable gap and independent trajectories exist. Split by drill family, initial state, and disturbance regime to avoid leakage. Quantized and fine-tuned artifacts must rerun the same held-out scorecard.

Gate: reproducible useful improvement with no unacceptable regression. No training recipe, model family, or hardware purchase bypasses this evidence.

## 3. Connect the synthetic Ignition lab and peb

Use a separately installed lab gateway with simulator tags. Verify the exact supported vendor/plugin versions and trial limitations. Define a minimal tag/alarms read adapter and test forbidden routes, credentials, configuration calls, scripting calls, request tampering, and network failure. Pin transport compatibility instead of assuming the latest MCP revision works with an older module.

Agree on peb's public integration contract. Do not equate its observe mode with a shadow mode or its schema compliance with voluntary behavioral integrity. Persist external evidence anchors and reconcile source/agent/gateway receipts. Keep the synthetic command experiments, if separately authorized later, outside this advisory server.

Gate: actual source reads are receipted, denied operations are demonstrated, and simulated failures withhold advice or explicitly narrow its scope. The current repo does not claim this gate passed.

## 4. Latency and operator evaluation

Benchmark the actual useful model and realistic context on existing hardware. Measure time to first useful answer, stale-result withholding, cancellation, throughput, and peak memory. Test whether operators correctly distinguish observations, hypotheses, recommendations, and withheld advice.

Gate: measured operator and latency requirements are met. Hardware purchases follow a demonstrated gap.

## 5. Any plant conversation

This belongs to the plant's engineers and change process. It requires approved data provenance, procedures, system boundaries, access review, threat analysis, operating ownership, and acceptance evidence. This lab, its passing tests, and any human approval within it grant no plant access or control authority.
