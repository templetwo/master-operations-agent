# Adoption of explanation task v1.1

Recorded by the MacBook seat (claude-opus-5-5) on `Anthonys-MacBook-Pro.local`, 2026-10-03.

## The adoption

Anthony adopted [explanation-task-v1.1.md](explanation-task-v1.1.md) on 2026-10-03. His words, typed in this Claude Code session, are quoted exactly:

> as recomended

They answered the request to approve the spec and its ten decisions, where "all as recommended" was offered as a sufficient answer. The seat's message just before asked for "Your approval of the v1.1 spec and the 10 decisions ('all as recommended' is enough)".

The adopted bytes are:

- `docs/explanation-task-v1.1.md` at commit `e900abf`;
- git blob `c364fa14b947d09bd57cee520dc8c0b0e4fa580a`;
- sha256 `020699afd7be8d35a424e3df34339172735c0f196bd0e437a8da34d69b163dae`.

That file is not edited. Its status line still reads "draft, not adopted", because these are the bytes he approved. This record is what makes them adopted.

## Decisions, each as recommended

1. v1.1 is a revision of v1, not a new task.
2. Caps are those of section 4: 12 claims, 4 causes, 8 `missing` items, 8 `missing_evidence` items, 240 characters per free-text item, and 2400 characters in total.
3. Verbatim catalog check sentences whose id is in the packet kernel are allowed in `missing_evidence` and are not recommendations.
4. If preflight finds ineligible packets in the existing package, the case author issues a corrected case freeze, reviewed again, before any run.
5. Outputs are shuffled per packet so the reviewer cannot tell the template from a model, and the label is hidden from the review sheet.
6. Mechanical checks stay advisory beside the sheet. He accepts any result per case in his own words. There is no blanket delegation.
7. The eligible reason list is as written in section 1.
8. The timestamp pattern, the leak check and the duplicate-excerpt rule make packets ineligible.
9. The section 5 abstention-fit rule applies.
10. Freezing the grid for the existing package is a new case freeze, recorded by the case author or by him.

## Protocol event, recorded as section 9 requires

- The spec was revised after the existing case package was authored against v1.
- No candidate had run on that package when this revision was adopted. The evidence for that is the exposure ledger on the Stack and this repository's history. This repository holds no explanation runner, template or evaluator before this adoption.
- What changed is listed in the supersession table of v1.1. The case bytes did not change, and nobody who wrote or reviewed v1.1 read them.

## What this adoption does not do

- It does not authorize a model run.
- It does not run the evaluator on the existing package. Per section 10, that run needs the build committed, the grid frozen, and a recorded independent review of the case freeze.
