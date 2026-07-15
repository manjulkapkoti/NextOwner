# NextOwner

A marketplace for buying and selling small online businesses — an online M&A marketplace MVP ,a two-sided platform where founders sell their profitable online businesses (SaaS, ecommerce, agencies, etc.) and buyers (solo entrepreneurs, PE firms, strategics) take over them. It is built for learning, **entirely local** (no cloud account needed). Planning phase is complete; development starts at **Milestone 0**.

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
├── app/                       # React SPA        — created at Milestone 0
├── backend/                   # FastAPI backend  — created at Milestone 0
└── seed/                      # demo-data script — created at Milestone 0
```

## Documentation map

| Read this…                                                         | …for                                                                                                                                                                                          |
| ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`docs/design_implementation.md`](./docs/design_implementation.md) | **Start here.** The business explained from zero (Part 1), every architecture component (Part 2), local dev setup (Part 3), the milestone build guide (Part 4), Supabase alternative (Part 6) |
| [`docs/acquire_design.md`](./docs/acquire_design.md)               | The original Acquire.com research: tech stack, feature list, MVP subset, FR-1…23 + NFRs                                                                                                       |
| [`docs/testing_guide.md`](./docs/testing_guide.md)                 | Test framework setup + per-milestone test checklists (tests = executable acceptance criteria)                                                                                                 |
| [`specs/000-constitution.md`](./specs/000-constitution.md)         | The rules every spec and line of code must follow                                                                                                                                             |
| [`docs/agentic_scope.md`](./docs/agentic_scope.md)                 | Post-MVP AI/agentic roadmap (deal-scout, diligence agent, …)                                                                                                                                  |
| [`docs/research/synthesis.md`](./docs/research/synthesis.md)       | Cross-company synthesis: the market map, 7 category laws, stack comparison, decisions ledger, NextOwner's white space                                                                         |
| [`docs/research/`](./docs/research/)                               | Individual competitor teardowns + [`cool_features.md`](./docs/research/cool_features.md) (adopted & backlog ideas)                                                                            |
| [`docs/temp_readme.md`](./docs/temp_readme.md)                     | Q&A notes: milestones-as-phases, spec-driven development workflow                                                                                                                             |

## Stack (constitution Article 1)

React + Vite + MUI + MobX · **Python FastAPI** · SQLModel · SQLite → Postgres · JWT auth · WebSockets for chat · pytest / Vitest / Playwright · single-origin `/api` layout · third-party vendors (Stripe, Persona, Escrow) **mocked locally**.

## Development workflow (SDD loop)

```
pick milestone (docs/design_implementation.md Part 4)
→ write specs/NNN-name/spec.md (user stories + GIVEN/WHEN/THEN, cite FRs)
→ write its tests from the checklist (docs/testing_guide.md) — they fail
→ implement → tests pass → full suite green
→ tech-lead + appsec review & test on the branch → open PR (agent-vetted) → you approve → squash-merge → next milestone
```

Next action: **Milestone 0** — scaffold `app/` + `backend/` per `docs/design_implementation.md` §3.3–3.4, prove the pipeline with `GET /health`, then write `specs/001-auth-roles/spec.md`.
