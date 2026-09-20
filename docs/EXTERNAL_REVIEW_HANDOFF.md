# External review handoff: repeated model failures

Prepared 2026-09-20 for an outside reviewer. This is a maintainer-prepared brief, not an independent review or endorsement. Please challenge the harness, policy, tests, and conclusions as well as the models.

**Follow-up work:** this handoff describes the frozen `dd40e9d` / `7451a72` review baseline. Later runtime and diagnostic changes, controlled experimental outcomes, and private holdout preparation are documented in [the v0.6 completion receipts](../receipts/v0.6/README.md). Statements below about unresolved defects are historical findings at that baseline; original evidence remains intact.

## Review request and public entry points

The unresolved problem is repeated **0/10 useful assessments** across tested local and cloud configurations. We can show that the application withholds invalid candidates. We have not shown that an LLM adds useful operations reasoning. Please determine which failures come from our integration and task specification, which come from model behavior, and whether the current task is a sensible use of an LLM at all.

- [Public repository](https://github.com/templetwo/master-operations-agent)
- [Latest branch: main](https://github.com/templetwo/master-operations-agent/tree/main)
- [Latest version of this handoff](https://github.com/templetwo/master-operations-agent/blob/main/docs/EXTERNAL_REVIEW_HANDOFF.md)
- [Frozen code and completed inference receipts under review](https://github.com/templetwo/master-operations-agent/tree/dd40e9dd8b777c2dc4efc35cb397e165334227c1)
- [Latest publication and clean-checkout receipts](https://github.com/templetwo/master-operations-agent/tree/main/receipts/external-review)

`main` is a moving link. The frozen commit is `dd40e9dd8b777c2dc4efc35cb397e165334227c1`; subsequent handoff/publication commits do not change the runtime or repair the observed failures. Historical experiments retain their own source hashes and settings. Do not assume a historical run used today's prompt merely because its receipts appear on `main`.

## What actually exists

This is a Python standard-library synthetic advisory workbench, version 0.5.0. A Node adapter creates isolated headless simulator instances and exports five operator-visible indications over a 120-second window. The agent has four allowed reads, a six-response budget, and a 60-second observation freshness limit. Provider candidates are validated independently of generation; accepted IDs become fixed catalog text. No model-written freeform operating instruction is released.

The default provider is deterministic. Other tested paths are explicit local Ollama inference and a separate opt-in DeepSeek synthetic comparison. There is no Ignition connection, peb integration, training pipeline, live plant input, control tool, or demonstrated plant readiness. The larger original roadmap is not an implementation inventory. Read the [architecture](architecture.md), [drill contract](drills.md), and [remaining gates](roadmap.md).

The original repository had no remote when this review handoff was requested. Public publication is part of this handoff, not something earlier local commits had already accomplished.

## Evidence-first reading order

1. [Latest actual DeepSeek report](../receipts/v0.5/deepseek-live-network/README.md), its [comparison](../receipts/v0.5/deepseek-live-network/comparison.json), [audit](../receipts/v0.5/deepseek-live-network/audit.json), and [full event export](../receipts/v0.5/deepseek-live-network/cloud-model.json).
2. [V0.4 local diagnosis and results](../receipts/v0.4/README.md), especially the [schema-order experiment](../receipts/v0.4/schema-order-4b/run.json) and [final 9B comparison](../receipts/v0.4/qwen35-9b-read-state/comparison.json).
3. [V0.3 original failures](../receipts/v0.3/README.md). Some uncertainty described there was later resolved in v0.4; these historical notes are preserved.
4. [Engine and prompt](../moa/engine.py), [policy and deterministic oracle](../moa/knowledge.py), [local transport and baseline](../moa/providers.py), [DeepSeek transport](../moa/deepseek.py), [scorecard](../moa/drills.py), and [explicit expected answers](../moa/data/drills-v1.json).
5. [Clean-checkout validation](../receipts/external-review/clean-checkout/validation.json) and its named test output. Passing mocked tests do not establish actual model capability.

## Results, with the right denominators

The 18-case development suite has ten usable cases and eight input-guard cases. It uses six recipes at two seeds, plus six integrity perturbations. The ten usable cases are correlated development examples, not ten independently sampled operating regimes.

| Tested configuration | Required reads completed on usable cases | Accepted useful advisories | Evidence |
|---|---:|---:|---|
| V0.3 Qwen3 4B and Qwen3.5 9B configurations | 0/10 in each run | 0/10 in each run | [V0.3 index](../receipts/v0.3/README.md) |
| V0.4 Qwen3 4B, wire serialization corrected | 0/10 | 0/10 | [Comparison](../receipts/v0.4/qwen3-4b/comparison.json) |
| V0.4 Qwen3.5 9B, wire serialization corrected | 0/10 | 0/10 | [Comparison](../receipts/v0.4/qwen35-9b/comparison.json) |
| V0.4 Qwen3.5 9B, explicit remaining-read status added | 10/10 | 0/10 | [Comparison](../receipts/v0.4/qwen35-9b-read-state/comparison.json) |
| V0.5 DeepSeek `deepseek-flash`, non-thinking JSON mode | 10/10 | 0/10 | [Comparison](../receipts/v0.5/deepseek-live-network/comparison.json) |
| Deterministic reference in each comparison | Required reads performed | 10/10 | Baseline reports beside each comparison |
| Always-refuse negative control | Does not perform reads | 0/10 | Control reports beside each comparison |

All providers pass the eight input guards because those checks run before inference. That is application rejection behavior, not model irrelevance detection or learned restraint. A total of 8/18 would be a misleading model-quality headline. There is no measured BFCL score here.

The latest local and cloud runs share manifest, policy, system-prompt, and entry-message hashes. Their decoding constraints differ: Ollama receives a union JSON schema, while DeepSeek receives JSON-object mode. Local weights have reported artifact digests; the cloud alias is mutable. These runs do not support a general model-family ranking.

## Confirmed failure points

### 1. A harness defect caused an early protocol failure

The original request encoder recursively sorted JSON properties, including the response schema. This changed the order used for constrained generation. In an order-only 4B experiment, sorted/declared/declared/sorted schema order produced abstain/read/read/abstain with otherwise identical request values. The wire-order fix is real, and exact byte hashes were added. The [diagnosis](protocol-order.md) and saved requests allow inspection.

That evidence is strong for the tested setup. It is not proof that all refusals from every model arise from schema ordering. Early prompt iterations and a larger local model did not fix the defect. This is a concrete reason to investigate integration before attributing zero scores to weak models.

### 2. Completing the read sequence did not produce useful answers

After the serialization fix, models still skipped required reads. Explicit remaining-read messages brought the final 9B run to 10/10 complete read sequences. It then produced nine candidate-schema failures, including empty check lists, and one unsupported finding set. The model reached the task but did not satisfy its output requirements.

DeepSeek also completed all three required reads on every usable case. Of ten final candidates, eight added unexpected fields, one wrapped its advice inside a `content` object with `type: json_object`, and one passed shape validation but failed finding validation. The eight extra-field responses generally included `type: json_object`. The API setting may be confused with answer content, but its causal role has not been isolated by an experiment.

The validator did not unwrap candidates, delete fields, retry answers, or relax expected IDs. Fixing JSON shape alone has not been shown to fix the selected findings or checks.

### 3. A reported rejection subtotal is incomplete

In the latest DeepSeek report, `candidate_rejections` is 2. The implementation counts named semantic/candidate errors but omits the generic `schema` code returned for unexpected candidate fields. The case records show eight additional schema failures, so all ten usable candidates were rejected. The [audit](../receipts/v0.5/deepseek-live-network/audit.json) explains the discrepancy. Historical reports remain unchanged, and the aggregate implementation is still unfixed in the reviewed code.

A repair should classify failures by stage as well as reason. Simply counting every generic schema failure as a candidate failure could misclassify malformed input or tool arguments. A reviewer should require a regression that distinguishes those paths.

### 4. Passing tests and a passing baseline have limited meaning

The deterministic baseline and independent candidate validator both call `knowledge.eligible()`. They are separated from the LLM, but they are not independent implementations of process truth. The manifest's expected answers are explicitly authored rather than computed through that function, yet both the policy and expectations lack independent controls review.

The positive mocked cloud integration returns baseline behavior. It proves that the transport/runner can carry a conforming answer through actual simulator exports. It does not show that a real model can infer that answer. The current task is exact replication of a small deterministic policy, which already runs faster and passes its own development suite without an LLM.

## Review hypotheses and specification risks

These are inspection findings and questions, not established causes of every failure.

- **Incomplete policy presentation.** `TREND_RULES["checks"]` says to retain snapshot checks. `eligible()` specifies which checks accompany alarms or no alarms, including a special demo-profile override, but `POLICY` does not state that complete mapping as an explicit rule table. The system prompt says to use appropriate catalog checks. Determine whether a model is being scored against requirements it was not fully told.
- **Exact equality bundles different error severities.** `validate_candidate()` requires exact sets of findings, checks, and evidence. Missing a required warning, adding an unsupported causal claim, adding an unnecessary review check, and using the wrong envelope can all yield zero usefulness. Preserve the release boundary, but report the distinct failures before drawing capability conclusions. Any alternate semantic rubric needs independent review and a versioned definition.
- **The task may not need an LLM at this layer.** Ask what measurable benefit the model should add over the existing deterministic calculation. Potential later tasks such as explanations, missing-evidence questions, or document retrieval are not implemented or evaluated here. Do not assume broad agent branding establishes a use case.
- **Development-set reuse.** Prompts and protocol messages were iterated against the same cases. There is no frozen independent holdout, controls-engineer label review, or demonstrated generalization across process units. New prompts should be evaluated as new development experiments, not retroactive repairs to a held-out score.
- **Protocol-specific difficulty.** Tools are requested through JSON assistant text and returned as user messages, rather than using each provider's native function-call mechanism. The six-turn budget, 768-token output cap, non-thinking setting, schema union, and catalog presentation could affect success. Their separate effects remain unmeasured.
- **Telemetry can be overinterpreted.** A received tool result proves delivery to the model context, not comprehension. Cloud median latency of 4.317 seconds and local median of 19.72 seconds describe withheld attempts, not useful-answer latency. Non-streaming calls do not measure time to first token. Evidence fidelity of 0/0 is undefined coverage, not success.
- **Evidence is local.** Hash chains detect inconsistency relative to a retained head, not whole-history replacement by a privileged local writer. Public commit hashes now give reviewers a stable copy to inspect; they do not independently attest the original API calls or runtime environment. Full JSON event exports are tracked; SQLite databases are ignored.
- **Operational scope is narrow.** Provenance labels are declarations, not authentication. Local daemon isolation and cloud model identity have limits documented in the receipts. None of this implements an industrial authorization boundary or demonstrates resistance to arbitrary malicious evidence.

## Reproduce without an API key

Python 3.10 or newer is declared; the recorded validation used Python 3.14.6. Node is required for the simulator adapter. No third-party Python runtime package is needed when running from the checkout. Use a new directory for output and inspect the trusted simulator source before executing it.

```sh
git clone https://github.com/templetwo/master-operations-agent.git
git clone https://github.com/templetwo/experion-station-sim.git
git -C master-operations-agent checkout dd40e9dd8b777c2dc4efc35cb397e165334227c1
git -C experion-station-sim checkout 3aad7695b8720b291999ef0903fcab7b7e008f1e
cd master-operations-agent
python3 -m unittest discover -s tests -v
python3 scripts/validate.py --sim-repo ../experion-station-sim --output receipts/reviewer-local
```

The first test command skips optional simulator tests without `MOA_SIM_REPO`. The validation script sets it for the second run, executes the full suite, smoke scorecard, JavaScript syntax checks, and deterministic simulator drills. Local HTTP boundary tests need permission to bind loopback. DeepSeek tests use mocked transport; these commands make no actual cloud inference calls. The exact local clean-checkout validation is saved in the publication receipts.

For a new paid cloud experiment, see [DeepSeek setup](deepseek.md). Use your own key outside the repository and an explicit synthetic-cloud flag. Credentials are not included in this handoff. A new call to a mutable service alias is not a byte-identical reproduction of the September 20 run. Local replay also requires the recorded model artifact and serving environment; no model weights are bundled.

## Requested reviewer deliverable

Please return a prioritized written review with file/line or receipt references, separating confirmed defects, plausible causes requiring experiments, and unsupported product claims. Start with the first rejected candidate in each latest run and trace the exact input, available policy, response, and rejection path.

Then propose the smallest experiment that distinguishes output-format failure from policy misunderstanding without revealing expected answers to the model. A useful sequence would freeze this baseline, make the output contract explicit without case labels, separately make the complete policy mapping explicit, and compare each change independently. Diagnose boundary arithmetic and check selection with independently authored examples. Any diagnostic normalization of a saved response must remain offline and clearly separate from released advice and original scores.

Recommend whether to keep deterministic decisions and use an LLM only where it demonstrates additional value. Define independently reviewed holdouts and promotion criteria before the next model-selection claim. Do not fix the recurring zero by weakening the validator, changing answers after seeing outputs, or counting pre-model input guards as model safety.

The desired outcome of this review is a falsifiable diagnosis and a small, justified next change. It is not a recommendation to buy hardware, fine-tune a model, or connect a plant.
