# Next research question: useful explanations

The current task asks a model to reproduce a small deterministic policy. Passing it shows compliance with that contract, not a reason to use a model instead of the calculation. The next task should measure whether a model makes already calculated findings easier to understand.

Proposed input: synthetic observations, the deterministic findings and checks, and a bounded set of engineering-document excerpts with stable source identifiers. Proposed output: a short explanation linking each factual claim to an observation or excerpt, an explicit distinction between observed facts and unconfirmed causes, and the missing evidence needed to distinguish those causes. No tool may change simulator or external state.

Compare with a deterministic template using the same input. Before implementation or inference, define an independent rubric for citation support, factual contradictions, causal overstatement, omitted uncertainty, readability and reader task completion. Use separate case authors and reviewers, and freeze a new evaluation set that neither candidate has seen. Count abstention separately from a supported explanation. An explanation with plausible prose and unsupported citations fails its evidence criterion.

Promotion would require a predefined, measurable benefit over the template while meeting the evidence criteria. This document does not choose a numerical threshold or claim a benefit. A controls engineer must help establish domain adequacy before any plant-facing use. The u1-v1 holdout remains a policy-compliance evaluation and is not reused to tune this task.

Status: proposal only. No explanation generator, additional model calls or expanded authorization path is implemented here.
