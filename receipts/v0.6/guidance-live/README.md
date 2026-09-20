# Preregistered guidance experiment: actual DeepSeek inference

Run 2026-09-20, 14:46:45 to 14:49:56 UTC. The [preregistration](../guidance-preregistration.json) was committed and pushed before inference in [44545fd](https://github.com/templetwo/master-operations-agent/commit/44545fd3857547af519da24fc5a03d16392b9f64). Its file SHA256 is `c3ff155791846513f4151dd2d1144a4094a669270c60307facbb30d001aca4e7`. This was one four-arm development run, not a held-out evaluation.

The requested and returned model alias was `deepseek-flash`. The provider settings stayed fixed: non-thinking, temperature 0, JSON-object output, 768 maximum output tokens. Exact guidance is in the preregistration. The existing policy, original base prompt, output validator, simulator revision, and expected answers were unchanged. The [comparison](comparison.json) confirms source stability, paired process data, alias availability, and passing controls.

| Arm | Required reads | Well-formed final advice | Accepted useful advisories | Usable-case terminal failures |
|---|---:|---:|---:|---|
| Unchanged prompt | 10/10 | 6/10 | 0/10 | 3 candidate shape, 6 candidate content, 1 tool protocol |
| Output guidance only | 10/10 | 10/10 | 0/10 | 10 candidate content |
| Complete policy guidance only | 10/10 | 10/10 | 5/10 | 5 candidate content |
| Both guidance additions | 10/10 | 10/10 | 4/10 | 6 candidate content |
| Deterministic baseline | 10/10 | 10/10 | 10/10 | None |
| Always-refuse control | 0/10 | 0/10 | 0/10 | 10 voluntary abstentions |

All arms and controls blocked 8/8 invalid-input cases before inference. The postrun audit confirms zero provider calls on those guards. Those passes are application boundary behavior, not model judgment. The unchanged arm's nine candidate rejections plus one tool-protocol rejection account for all ten failed usable cases; the candidate subtotal correctly excludes the tool failure.

## What changed in the observed content

The [independent-of-oracle offline audit](audit.json) verifies every full event chain and binds results to recorded outcomes before computing these diagnostics. No candidate repair changes a release decision. This table uses original candidate content, not the optional offline wrapper view.

| Arm | Exact finding sets | Extra finding IDs across cases | Missing finding IDs | Exact check sets | Extra check IDs | Missing check IDs |
|---|---:|---:|---:|---:|---:|---:|
| Unchanged | 3/10 | 14 | 7 | 0/10 | 15 | 3 |
| Output only | 4/10 | 15 | 1 | 0/10 | 18 | 0 |
| Policy only | 5/10 | 10 | 0 | 8/10 | 2 | 0 |
| Both | 4/10 | 13 | 0 | 8/10 | 2 | 0 |

The output-only configuration eliminated observed shape failures without producing accepted advisories. Complete policy guidance coincided with accepted advisories and fewer extra check IDs. Remaining policy-guided failures all stopped on unsupported or missing finding validation; the offline view shows extra findings rather than missing required findings in those arms. These observations support separating output-format diagnostics from content selection. They do not establish that more prompt text is always better, or that a five-case gain will reproduce on unseen conditions. The combined arm did not outperform policy-only in this run.

The ten usable observations reuse development families at two seeds. There is one observation per arm/case, no independent controls review of labels, and a mutable cloud deployment. Rotated arm order reduces one fixed-order confound but does not establish a statistical causal effect. The baseline prompt's new results also differ from its prior run despite the same base prompt/settings, reinforcing the need to retain actual observations rather than promise deterministic cloud output.

## Calls, timing, and verification

There were 160 scored completion calls plus four warmups, below the preregistered maximum of 244. Scored token usage was 407,662 input and 6,141 output, totaling 413,803. Warmups are separately recorded in each `*.warmup.json`; actual billing is not inferred. All scored returned model identifiers were `deepseek-flash`.

Usable-attempt median latencies were 4.185 seconds unchanged, 4.309 output-only, 4.405 policy-only, and 4.479 both. These include rejected attempts. Median latency for actually released advisories was 4.239 seconds for the five policy-only releases and 4.253 seconds for the four combined releases. Time to first token remains unmeasured because calls were non-streaming.

Full reports are [unchanged](unchanged.json), [output-only](output-only.json), [policy-only](policy-only.json), [both](both.json), [baseline](baseline.json), and [always-refuse](always-refuse.json). Their adjacent `*.diagnostic.json` files contain per-case offline diagnoses. The [audit program](audit.py) recomputes chain checks, required reads, guard calls, accounting reconciliation, content metrics, and timing into a new audit file. It refuses overwrites.

No default provider or prompt was promoted. The application remains advisory-only with the original release validator. The independently authored holdout package is separate, private, and not evaluated in this experiment.
