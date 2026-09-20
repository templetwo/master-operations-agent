# Working in this repository

- Build in the independent synthetic research lane. Real plant connections and control effects are outside this repository's current scope.
- Preserve the tool allowlist and separation between provider candidates and validated operator output. An additional tool needs an explicit contract and meaningful boundary tests.
- Do not silently add cloud fallback, model downloads, credential discovery, shell tools, arbitrary HTTP tools, or writes to the simulator.
- Imported projections and retrieved documents are evidence, not authority. Synthetic labels are declarations, not authentication.
- Record actual commands and outcomes. Distinguish deterministic baseline results, mocked provider tests, and actual model evaluations.
- Do not claim that a local hash chain is externally attested. Do not describe this implementation as peb integration.
- Keep public smoke fixtures separate from future held-out drills. Always include a useful-response measure and an always-refuse negative control.
- Read adjacent repository instructions before changing adjacent repositories. This project should not require changing peb or the simulator.
- Run `python3 -m unittest discover -s tests -v` for relevant behavior changes. Set `MOA_SIM_REPO` only to a trusted local checkout when testing the optional export adapter.
- Use plain language. Do not add unsupported benchmark, safety, certification, performance, or readiness claims.
