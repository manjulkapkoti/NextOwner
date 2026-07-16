# NextOwner

A marketplace for buying and selling small online businesses — an online M&A marketplace MVP, a two-sided platform where founders sell their profitable online businesses (SaaS, ecommerce, agencies, etc.) and buyers (solo entrepreneurs, PE firms, strategics) take over them. It is built for learning, **entirely local** (no cloud account needed). Planning is complete and **Milestone 0** (scaffold + health check) has shipped; development continues at **Milestone 1** (auth & roles) — see [`docs/milestones.md`](./docs/milestones.md) and [`docs/progress.md`](./docs/progress.md).

## Project structure

```
NextOwner/
├── README.md                  ← you are here
├── docs/                      # all research & guides (see map below)
│   ├── diagrams/              # architecture & workflow diagrams (.excalidraw + .html)
│   │   └── diagGenerator/     # diagram sources + generator scripts (see its README)
│   └── research/              # competitor teardowns (Acquire, Baton, Exitwise, Little Exits)
├── specs/                     # spec-driven development artifacts
│   └── 000-constitution.md    # binding decisions: stack, principles, process, conventions
├── app/                       # React SPA        — shipped at Milestone 0
├── backend/                   # FastAPI backend  — shipped at Milestone 0
└── seed/                      # demo-data script — arrives with M4 (marketplace browse)
```

## Documentation map

| Read this…                                                         | …for                                                                                                                                                                                          |
| ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`docs/design_implementation.md`](./docs/design_implementation.md) | **Start here.** NextOwner's design, and only NextOwner's: the business explained from zero (Part 1), the architecture — stack, data model, NDA gate, horizontal scale (Part 3), the milestone build guide (Part 4), the mental model (Part 5) |
| [`docs/requirements.md`](./docs/requirements.md)                   | **NextOwner's requirements source of truth** — MVP scope (F1–F12), FR-1…23, NFRs. **Specs cite this.**                                                                                        |
| [`docs/research/acquire_design.md`](./docs/research/acquire_design.md) | The Acquire.com teardown: tech stack, architecture + component walkthrough, feature list. **Reference only — binding on nobody.**                                                          |
| [`docs/testing_guide.md`](./docs/testing_guide.md)                 | Test framework setup + per-milestone test checklists (tests = executable acceptance criteria)                                                                                                 |
| [`specs/000-constitution.md`](./specs/000-constitution.md)         | The rules every spec and line of code must follow                                                                                                                                             |
| [`docs/agentic_scope.md`](./docs/agentic_scope.md)                 | Post-MVP AI/agentic roadmap (deal-scout, diligence agent, …)                                                                                                                                  |
| [`docs/research/synthesis.md`](./docs/research/synthesis.md)       | Cross-company synthesis: the market map, 7 category laws, stack comparison, decisions ledger, NextOwner's white space                                                                         |
| [`docs/research/`](./docs/research/)                               | Individual competitor teardowns + [`cool_features.md`](./docs/research/cool_features.md) (adopted & backlog ideas)                                                                            |
| [`docs/security.md`](./docs/security.md)                           | **Binding.** End-to-end threat model + security checklist — security is the owner's #1 priority                                                                                               |
| [`docs/error_handling.md`](./docs/error_handling.md)               | The product's failure contract (error shapes, backend/frontend patterns, vendor failure modes)                                                                                                |
| [`docs/data_protection.md`](./docs/data_protection.md)             | The technical privacy slice (PII inventory, data minimization, erasure-ready schema, KYC-via-vendor)                                                                                          |
| [`docs/milestones.md`](./docs/milestones.md)                       | The milestone runbook: the per-milestone loop, the M0→M12 checklist, scope fold-ins, progress tracker                                                                                         |
| [`docs/git_strategy.md`](./docs/git_strategy.md)                   | Branch → PR → squash-merge workflow; the pre-PR branch review; conflict recovery                                                                                                              |
| [`docs/session_recovery.md`](./docs/session_recovery.md)           | Resume across sessions: `/checkpoint`, `/resume`, the crash-proof flight recorder                                                                                                             |

## Stack (constitution Article 1)

React + Vite + MUI + MobX · **Python FastAPI** · SQLModel · SQLite → Postgres · JWT auth · WebSockets for chat · pytest / Vitest / Playwright · single-origin `/api` layout · third-party vendors (Stripe, Persona, Escrow) **mocked locally**.

## Development workflow (SDD loop)

```
pick milestone (docs/design_implementation.md Part 4)
→ write specs/NNN-name/spec.md (user stories + GIVEN/WHEN/THEN, cite FRs)
→ write its tests from the checklist (docs/testing_guide.md) — they fail
→ implement → tests pass → full suite green
→ review & test on the branch (inline; + an appsec pass on security-critical milestones) → open PR (vetted) → you approve → squash-merge → next milestone
```

Next action: **Milestone 1** — `/run-milestone auth-roles --pause-after-spec` (M0 is done; the live resume point is always `docs/progress.md` / `/resume`).
