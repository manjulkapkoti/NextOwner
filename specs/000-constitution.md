# Spec 000 — Project Constitution

> Binding decisions for **all** feature specs in this project. Every `spec.md` / `plan.md` under `specs/` must comply with this document. Amending an article requires updating this file (with date + reason) and checking existing specs for impact.
>
> Reference documents: [`acquire_design.md`](../docs/acquire_design.md) (requirements FR-1…FR-23, NFRs), [`design_implementation.md`](../docs/design_implementation.md) (architecture & milestones), [`testing_guide.md`](../docs/testing_guide.md) (test framework & per-milestone checklists), [`agentic_scope.md`](../docs/agentic_scope.md) (future AI roadmap).

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
- *Pydantic* validates agent tool arguments and structured LLM outputs with the same schema system used for API requests; *WebSockets* (chat) are the reuse path for streaming agent progress; *SQL* hosts agent memory, run logs, and comps data (pgvector after the Postgres swap).
- *Planned additions when agents arrive (additive, not corrective):* a job runner + `agent_runs`/`agent_steps` tables for long-running execution and tracing; golden-set evals as pytest cases; the Postgres swap likely moves earlier once concurrent agent writes appear.
- *Principle:* agent loops are built directly on the model provider's SDK, with tools exposed via plain functions/MCP — no heavyweight agent frameworks. **The agent loop is code we own.**

**Considered and rejected:**
- *Firebase (Acquire's real stack, via Emulator Suite)* — maximum case-study fidelity and free realtime, but TypeScript-only backend and proprietary rules language. Documented in `design_implementation.md` Part 2.
- *Supabase (BaaS, no custom backend)* — fastest path, but less is learned and backend logic wouldn't be Python. Kept as reference in `design_implementation.md` Part 6.

## Article 2 — Architecture Principles

1. **The API is the only door.** The browser never talks to the database; every privilege check lives in a FastAPI dependency (`permissions.py`) — one function per trust boundary.
2. **Public/private split.** Anonymous listing data and NDA-gated data live in separate tables served by separate endpoints; public response models must make identity-field leaks impossible by schema.
3. **Status state machines are the business.** `listing.status`, `offer.status`, `access_request.status` encode the workflow; transitions happen only inside endpoints that validate the move. Clients never set status fields directly.
4. **Never trust the client** for `owner_id`, `sender_id`, `status`, prices in privileged flows — the server derives them from the JWT and the database.
5. **Audit what matters:** offers and access decisions get timestamped event rows.

## Article 3 — Development Process

1. **Spec-driven:** each milestone (Part 4 of `design_implementation.md`) gets `specs/NNN-name/spec.md` (user stories + GIVEN/WHEN/THEN acceptance criteria + FR references) and `plan.md` (schema deltas, endpoints, components) *before* implementation. Spec just-in-time — one or two milestones ahead, no further.
2. **Tests are the acceptance criteria:** every GIVEN/WHEN/THEN becomes exactly one test (`testing_guide.md`); write them failing before implementing.
3. **Definition of done:** a milestone is done when its tests pass **and** the full `npm test` suite is green. Commit only when green.
4. **Milestone order is binding** (M0→M11 as sequenced in Part 4); Phase E items (M8–M11) may be reordered among themselves.

## Article 4 — Conventions

- **Product name: NextOwner** (decided 2026-07-13). Use it in all user-facing strings, app titles (`FastAPI(title="NextOwner API")`), and branding; local SQLite file is `nextowner.db`. The repo folder may remain `AcquireMVP` — renaming it is optional and cosmetic. Before public launch: verify domain availability and run a USPTO trademark search (class 35/36).
- Folder layout as defined in `design_implementation.md` §3.3 (`app/`, `backend/app/{routers,services}`, `backend/tests/`, `seed/`, `specs/`).
- REST style: plural nouns (`/listings`), sub-resources for ownership (`/listings/{id}/private`), POST verbs only for state transitions (`/listings/{id}/submit`, `/offers/{id}/accept`).
- **Single-origin layout:** all backend routes mounted under the `/api` prefix (WebSockets under `/ws`); locally the Vite dev proxy forwards both to FastAPI (no CORS); production uses one domain with path routing (reverse proxy → SPA build + FastAPI). Doc prose may omit the `/api` prefix; code never does.
- **NDA model:** one platform-wide NDA signed once per user (`users.nda_signed_at`), plus per-listing access requests approved by the seller (`requested → approved|denied`). Adopted from Baton research (`docs/research/baton_design.md`).
- Error codes: 401 unauthenticated, 403 forbidden, 404 not found, 409 invalid state transition, 422 validation (Pydantic default).
- Feature flags in a plain `flags.py` / `flags.ts`; analytics through a local `track(event, props)` wrapper (console only for now).
- Spec numbering: `000` constitution, then `001+` in build order matching milestones.

---

*Amendment log:*
- 2026-07-13 — v1. Initial constitution; backend stack changed from the original Firebase-mirror plan to Python FastAPI (see Article 1).
- 2026-07-13 — Product named **NextOwner** (Article 4).
- 2026-07-13 — Adopted from Baton research: one platform-wide NDA + per-listing access approval (affects Milestone 5 / FR-13), and single-origin `/api` path layout with Vite dev proxy (Article 4).
- 2026-07-13 — Agent-readiness note added to Article 1: stack confirmed as the recommended base for owner-controlled agent development; agents bound by the same permission gates as humans; no agent frameworks — loops built on the provider SDK.
