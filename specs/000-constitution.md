# Spec 000 — Project Constitution (Articles)

> Binding decisions for **all** feature specs in this project. Every `spec.md` / `plan.md` under `specs/` must comply with this document. Amending an article requires updating this file (with date + reason), **appending the entry to [`000-constitution-amendments.md`](./000-constitution-amendments.md)**, and checking existing specs for impact.
>
> **This file holds the rules in force. The reasoning behind them — every amendment, with the evidence and the near-miss that prompted it — lives in [`000-constitution-amendments.md`](./000-constitution-amendments.md), which is *not* loaded by default. Read it when you need to know *why* a rule says what it says, when you are about to change a rule, or when a rule seems wrong.** Split 2026-07-25 for context efficiency; nothing was deleted, and every rule the log still governed was promoted into the Articles below first (marked *[promoted from the log]*).
>
> Reference documents: [`requirements.md`](../docs/requirements.md) (**NextOwner's** requirements — MVP scope F1–F12, FR-1…FR-23, NFRs), [`design_implementation.md`](../docs/design_implementation.md) (architecture & milestones), [`testing_guide.md`](../docs/testing_guide.md) (test framework & per-milestone checklists), [`agentic_scope.md`](../docs/agentic_scope.md) (future AI roadmap), [`research/`](../docs/research/) (competitor teardowns + the rejected Supabase option — **reference only, binding on nobody**).

---

## Article 1 — Tech Stack (DECIDED 2026-07-13)

| Layer | Decision |
|---|---|
| Frontend | **React + Vite + TypeScript**, MUI (+ Emotion), MobX, react-router |
| Backend | **Python FastAPI** — the API is the only door to data |
| ORM / models | **SQLModel** (SQLAlchemy + Pydantic) |
| Database | **SQLite** locally now → **PostgreSQL** later (connection-string swap; no code rewrite) |
| Auth | JWT issued by our own FastAPI endpoints; bcrypt password hashing |
| Realtime (chat) | FastAPI **WebSockets** (polling acceptable as interim fallback) |
| File storage | Local `uploads/` folder, served only through permission-checked endpoints |
| Backend tests | **pytest** + FastAPI TestClient, in-memory SQLite per test |
| Frontend tests | Vitest + React Testing Library; Playwright E2E after Phase D |
| Third-party vendors (Stripe, Persona, Escrow.com, ChartMogul) | **Mocked locally** with production-shaped state machines; real integrations are post-MVP |
| Environment | **100% local** — no cloud account, no Docker required (Docker becomes optional only for the Postgres swap) |

**Rationale:** Python aligns with the planned agentic layer (`agentic_scope.md`); FastAPI's Pydantic validation and auto-generated `/docs` fit spec-driven development; SQL skills are the most transferable.

**Agent-readiness (recorded 2026-07-13)** — this stack was confirmed as the recommended base for owner-controlled agent development, for structural reasons that must be preserved as the code grows:

- *Same language:* agents are ordinary Python modules in the same service as the business logic — no cross-service glue to give an agent a tool. (Competitive note: no company in the researched category runs Python; the only shipped AI feature, Baton's Elena, was built against a TS stack.)
- *Permissions constrain agents structurally:* an agent runs **as** a scoped user through the same `permissions.py` gates (Article 2 applies to agents exactly as to humans) — it physically cannot exceed the rights of the identity it acts for. Never grant agents a rules-bypassing super-identity.
- *State machines + audit rows* (Article 2 #3, #5) mean agent actions go through the same legal-move validation and leave the same trace as human actions.
- *Pydantic* validates agent tool arguments and structured LLM outputs with the same schema system used for API requests; *WebSockets* (chat) are the reuse path for streaming agent progress; *SQL (Postgres)* hosts agent run logs, comps, and the **canonical** data, while **vectors live in a local vector store (Qdrant)** behind a `VectorStore` interface (pgvector kept as an option), populated by a **local embedding model** — Qdrant is a *rebuildable* index, so Postgres stays the source of truth.
- *Planned additions when agents arrive (additive, not corrective):* a job runner + `agent_runs`/`agent_steps` tables for long-running execution and tracing; golden-set evals as pytest cases; the Postgres swap likely moves earlier once concurrent agent writes appear.
- *Principle:* agent loops are built on a **thin, swappable model interface** — provider-agnostic, so a **local / open-source model** is a drop-in for a frontier one — with tools exposed via plain functions/**MCP**. **Prefer an owned thin loop; a framework may be adopted if the situation warrants (decided at build time).** Non-negotiable regardless: agents run **as scoped users through the gates**, and the security boundary lives in the core — not in the framework or the model.

**Considered and rejected:**
- *Firebase (Acquire's real stack, via Emulator Suite)* — maximum case-study fidelity and free realtime, but TypeScript-only backend and proprietary rules language. Documented in [`docs/research/acquire_design.md`](../docs/research/acquire_design.md) §2–§4.
- *Supabase (BaaS, no custom backend)* — fastest path, but less is learned and backend logic wouldn't be Python. Kept as reference in [`docs/research/supabase_alternative.md`](../docs/research/supabase_alternative.md).

## Article 2 — Architecture Principles

1. **The API is the only door.** The browser never talks to the database; every privilege check lives in a FastAPI dependency (`permissions.py`) — one function per trust boundary.
2. **Public/private split.** Anonymous listing data and NDA-gated data live in separate tables served by separate endpoints; public response models must make identity-field leaks impossible by schema.
3. **Status state machines are the business.** `listing.status`, `offer.status`, `access_request.status` encode the workflow; transitions happen only inside endpoints that validate the move. Clients never set status fields directly.
4. **Never trust the client** for `owner_id`, `sender_id`, `status`, prices in privileged flows — the server derives them from the JWT and the database.
5. **Audit what matters:** offers and access decisions get timestamped event rows. *[promoted from the log, 2026-07-20]* Before adding an event row, ask **what it preserves that the row itself loses** — an audit row earns its place only for values a later transition overwrites. Correspondingly, **adding a transition to a state machine can invalidate an audit design that was correct for the old one**; re-ask "what does this overwrite?" whenever a state machine grows.

## Article 3 — Development Process

1. **Spec-driven:** each milestone (Part 4 of `design_implementation.md`) gets `specs/NNN-name/spec.md` (user stories + GIVEN/WHEN/THEN acceptance criteria + FR references) and `plan.md` (schema deltas, endpoints, components, **and the Build order** — the implementation slices, one trust boundary each) *before* implementation. Spec just-in-time — one or two milestones ahead, no further.
   - *[promoted from the log, 2026-07-16]* **Spec time must read `docs/milestones.md` § Scope fold-ins** for the milestone being scoped — each fold-in bullet becomes acceptance criteria (plus its forbidden-path twin) in that spec.
   - *[promoted from the log, 2026-07-17]* **The Build order deliberately has no checkboxes and no status.** `plan.md` fixes the *order* (a design decision); **the red test list is the status**. A ticked box would be a second source of truth that lies after the first crash — which is precisely why `/resume` can rebuild a dead session from git + tests alone. Do not add checkboxes, and do not trust any that appear.
2. **Tests are the acceptance criteria:** every GIVEN/WHEN/THEN becomes exactly one test (`testing_guide.md`); write them failing before implementing.
   - *[promoted from the log, 2026-07-19]* **When a review finds a bug your tests missed, fix the bug, then ask what *class* of question your tests were not asking.** A negative test per *door* misses the corridor between them; the answer is usually a reachability test over sequences of actions, asserting the invariant rather than the endpoint.
   - *[promoted from the log, 2026-07-20]* **A test that passes before implementation is unverified** — TDD's guarantee is "it failed first." After writing the red set, assert that the number of passing new tests is zero; for any that do pass, prove they are regression pins rather than vacuous. Likewise, **a reachability or sabotage test nobody has seen fail proves nothing** — re-run the sabotage when you touch what it guards.
3. **Definition of done:** a milestone is done when its tests pass **and** the full `npm test` suite is green. Work happens on a per-milestone feature branch off `main`; commit freely on the branch (including the failing-tests-first commit). **Before the PR is opened**, the work is reviewed and tested **on the branch** (a pre-PR gate): the orchestrator reviews inline every milestone (architecture + the security must-cover matrix), plus one independent `appsec-engineer` pass on the security-critical milestones (M1/M2/M3/M5/M7/M8/M10) — opening a PR signals the work is vetted and ready for human approval. `main` is updated **only by merging a PR that is green** (tests + the security must-cover matrix) — never by a direct commit, so `main` is always green.
   - *[promoted from the log, 2026-07-19]* **The security-critical list is a floor, not the whole mechanism.** `scripts/check_appsec_trigger.py` reads the **diff** and requires an independent appsec pass whenever the branch touches a permission boundary, a route, a response model, a state transition, an upload path, money, or WebSockets — wired into `/dod` and `/run-milestone`. **A list predicts; a diff describes.** The trigger can only *escalate* beyond the list, never excuse a milestone on it.
   - *[promoted from the log, 2026-07-15]* Independent review agents are spawned **diff-scoped and in the background, with the model passed explicitly** — to keep context and usage low. The same applies to `docs-auditor` (`scripts/check_docs_trigger.py` decides when one is warranted). Give a review agent the diff **and** the binding documents: a contradiction lives between the diff and a file the diff never touched.
4. **Milestone order is binding** (M0→M12 as sequenced in Part 4 — M12 appended 2026-07-16); Phase E items (M8–M11) may be reordered among themselves.

## Article 4 — Conventions

- **Product name: NextOwner** (decided 2026-07-13). Use it in all user-facing strings, app titles (`FastAPI(title="NextOwner API")`), and branding; local SQLite file is `nextowner.db`. The repo folder is `NextOwner`. Before public launch: verify domain availability and run a USPTO trademark search (class 35/36).
- Folder layout as defined in `design_implementation.md` §3.3 (`app/`, `backend/app/{routers,services}`, `backend/tests/`, `seed/`, `specs/`).
- REST style: plural nouns (`/listings`), sub-resources for ownership (`/listings/{id}/private`), POST verbs only for state transitions (`/listings/{id}/submit`, `/offers/{id}/accept`).
- **Single-origin layout:** all backend routes mounted under the `/api` prefix (WebSockets under `/ws`); locally the Vite dev proxy forwards both to FastAPI (no CORS); production uses one domain with path routing (reverse proxy → SPA build + FastAPI). Doc prose may omit the `/api` prefix; code never does.
- **NDA model:** one platform-wide NDA signed once per user (`users.nda_signed_at`), plus per-listing access requests approved by the seller (`requested → approved|denied`). Adopted from Baton research (`docs/research/baton_design.md`).
- Error codes: 401 unauthenticated, 403 forbidden, 404 not found, 409 invalid state transition, 422 validation (Pydantic default).
- Feature flags in a plain `flags.py` / `flags.ts`; analytics through a local `track(event, props)` wrapper (console only for now).
- Spec numbering: `000` constitution, then `001+` in build order matching milestones.
  - *[promoted from the log, 2026-07-18]* **A foundation milestone inserted mid-sequence is named `pre-NNN-<slug>` and claims no number** (e.g. `specs/pre-003-app-shell/`), so neither the M-numbers nor the following spec numbers shift. This is the low-churn way to insert a milestone: any M-number or spec-number shift ripples through the security-critical list, `security.md` §7, `testing_guide.md` §5 and Part 4 — exactly the stale-reference churn to avoid. `/new-spec`'s "highest `NNN-*` + 1" scan skips a `pre-` prefix naturally.
- *[promoted from the log, 2026-07-18]* **One home per status claim.** Any status or state claim must have exactly one home, refreshed by an automatic trigger — **never by memory**. If you find one maintained by neither, either delete it and point at the single source, or fold it into the trigger. Duplicated truth is the repo's most persistent defect class: prefer a pointer over a copy, and where a copy must exist, date it and bind its refresh to a step nothing can route around (see `scripts/check_status_freshness.py`, which enforces the one fact needing no judgement — ***`main` contains only merged work***).
- *[promoted from the log, 2026-07-16]* **One file, one job.** A document that is simultaneously a competitor teardown and our requirements source will fuse the two and start prescribing a rejected architecture. A teardown's findings are worth keeping *as findings* — the failure mode is losing the attribution, not recording the fact. `docs/requirements.md` is what specs cite; `docs/research/` is reference only, binding on nobody.

---

*Amendment log: [`000-constitution-amendments.md`](./000-constitution-amendments.md) — 18 entries, 2026-07-13 → 2026-07-25. Not loaded by default; read it before changing any rule above.*
