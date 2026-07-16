# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status: M0 shipped — next: M1 (auth-roles)

Milestone 0 scaffolded the app: `app/` (React + Vite + TS SPA), `backend/` (FastAPI + SQLModel), the root `package.json` test orchestration, and the pytest/Vitest harness — `npm test` runs for real. Not yet built: `seed/` (arrives M4), all real domain tables and endpoints (M1+ — today only the throwaway `SandboxItem` / `/api/sandbox` pair exists, to be deleted at M1), and Playwright E2E (Phase D). `nextowner.db` is created on first run (gitignored). For the live "where are we": `docs/progress.md`, or run `/resume`.

Also runnable: the diagram generator under `docs/diagrams/diagGenerator/` (see `/gen-diagrams`).

## How we work: Spec-Driven Development (mandatory)

Every milestone follows this loop (constitution Article 3, `README.md`):

```
pick milestone (docs/design_implementation.md Part 4)
→ write specs/NNN-name/spec.md (user stories + GIVEN/WHEN/THEN + FR refs) and plan.md   ← before code
→ write its tests from docs/testing_guide.md §5 — they FAIL first
→ implement → tests pass → full `npm test` green
→ review & test on the branch (inline; + an appsec pass on security-critical milestones) → open PR (vetted) → you approve → squash-merge to main → next milestone
```

- **Every GIVEN/WHEN/THEN acceptance criterion becomes exactly one test, written failing before implementing.** If you can't write the test, the criterion is too vague — fix the spec.
- **Definition of done:** a milestone is done only when its tests pass **and** the full `npm test` suite is green, **and its PR merges** (see Git workflow below). Milestone order M0→M12 is binding (see `/start-milestone`, `/new-spec`, `/dod`); per-milestone **scope fold-ins** live in `docs/milestones.md` § Scope fold-ins — `/new-spec` reads them.

## Git workflow (branch → PR → merge)

`main` is protected — **never commit to it directly.** Every milestone's work happens on its own feature branch and lands via a PR.

- **One branch + one PR per milestone**, cut from fresh `main`: `git checkout main && git pull` → `git checkout -b feat/NNN-slug` (`feat|fix|chore`). All agents commit to that single branch; the orchestrator manages git, agents produce the code/tests.
- **Conventional Commits** (`feat:`/`fix:`/`test:`/`docs:`/`chore:`). Commit freely on the branch — including the **failing-tests-first** commit.
- **The green gate is the PR merge, not individual commits.** A PR merges to `main` only when `/dod` passes (tests + the `docs/security.md` §8 security matrix), so `main` is always green.
- **Flow:** `/start-milestone <name>` → `/new-spec` → failing tests → implement → `/dod` (green gate — full suite + security matrix; **does not open the PR**) → **branch review** (inline by the orchestrator every milestone — architecture + the §8 matrix — **plus** one independent `appsec-engineer` pass on the security-critical milestones M1/M2/M5/M7/M10) → fix findings → **open the PR** (push + `gh pr create`, once it's clean) → **you** review + approve → `/close-feature` (squash-merges + syncs `main`) → next milestone. The review happens **before** the PR exists; opening a PR means the work is vetted and ready for a human. (Inline-first keeps context/usage low; the `/dod` forbidden-path tests are the always-on security floor — see `docs/git_strategy.md`.)
- **Tooling:** `gh` CLI — `gh pr create` (open), `gh pr merge --squash --delete-branch` (human-approved merge).
- **Closing the feature (after approval):** `/close-feature [pr#]` queries the PR and runs `gh pr merge --squash --delete-branch` if it's still open (or just syncs if you already merged), then `git checkout main && git pull` — ready for the next branch. No passive notification; it queries on demand (or run it on a `/loop` to poll).
- **Full detail:** `docs/git_strategy.md` — the branch/PR rationale, the 9-step per-milestone flow, and conventions.

## Session continuity (resume across sessions)

Work spans days and a session can die mid-task (crash, closed tab, usage limit). To resume cleanly:

- **Start a session with `/resume`** — it reconstructs where you left off from git + `npm test` (the red tests are the to-do list) + `docs/progress.md`, trusting git+tests and self-healing if the status file is stale.
- **At a stopping point, run `/checkpoint`** — updates `docs/progress.md` (the "▶ next action"), commits WIP on the branch, pushes, and ensures a draft PR exists.
- **Crash-proof, automatic:** a `Stop` hook (`.claude/settings.json` → `.claude/hooks/flight_recorder.py`) rewrites the gitignored `.claude/session-state.md` every turn, so even an abrupt death leaves a fresh, recoverable snapshot — nothing depends on a graceful shutdown.
- **Full design + rationale:** `docs/session_recovery.md`.

## Non-negotiable architecture rules (constitution Article 2)

Violating these breaks the product's trust model. Apply them to agent code too — agents run *as* scoped users through the same gates, never with a bypass identity.

1. **The API is the only door.** The browser never touches the DB. Every privilege check lives in `backend/app/permissions.py` — one function per trust boundary.
2. **Never trust the client** for `owner_id`, `sender_id`, `status`, or prices in privileged flows — the server derives them from the JWT + DB.
3. **Public/private split.** Anonymous data (`Listing`) and NDA-gated data (`ListingPrivate`) live in separate tables served by separate endpoints. Public Pydantic `response_model`s must make identity leaks impossible *by schema*.
4. **Status state machines are the business.** `listing.status`, `offer.status`, `access_request.status` change only inside endpoints that validate the transition. Clients never set status fields directly.
5. **The NDA gate is the heart of the design.** `require_private_access` (`permissions.py`) guards private data and document downloads; `backend/tests/test_nda_gate.py` is the most important test file in the project.

## Security is priority #1 (owner's standing directive)

Security is the explicit top priority for this codebase — treat it as a first-class requirement in every spec, endpoint, and review, not an afterthought. The 5 rules above are the core; also apply these on **all** product code, and think adversarially (write the attacker's request, then block it):

- **Default-deny authorization on every non-public route.** No endpoint ships without an explicit `permissions.py` check. When in doubt, forbid. For every privileged action, write the **forbidden-path test** (wrong identity → 401/403/404, illegal transition → 409) *before* the happy path — these permission tests are the crown jewels (`docs/testing_guide.md` §1).
- **Validate every input at the boundary** with Pydantic/SQLModel schemas; reject mass-assignment of server-controlled fields (`status`, `is_admin`, `owner_id`, `verified`, prices). Only the DB layer's parameterized queries touch SQL — never string-build queries.
- **Secrets live in env only** (JWT signing key, future vendor keys) — never hardcoded, never logged, never committed (`.env` is gitignored). JWTs: bcrypt password hashing, signed tokens, verify signature + claims + expiry on every request.
- **Fail closed and don't leak.** Return correct status codes with generic client-facing messages; never surface stack traces, SQL, or internal detail. Public `response_model`s exclude private/identity fields by schema.
- **File uploads are hostile:** enforce type + size, normalize/confine paths (no traversal outside `uploads/{listing_id}/`), and serve only through permission-checked endpoints. WebSockets: verify JWT + membership on connect.
- **Agents get no bypass** — they act as scoped users through the same gates (Article 1).

If a change touches auth, permissions, data exposure, uploads, money, or WebSockets, call it out and cover it with negative tests before considering it done.

**The full threat model and end-to-end checklist is `docs/security.md`** — consult it when writing any spec (§7 per-milestone + §6 edge cases), endpoint/query/component (§1 the boundary you're crossing), or review (§8 touched→must-cover matrix). It is binding alongside the constitution.

## Stack (constitution Article 1)

React + Vite + TypeScript + MUI + MobX · **Python FastAPI** + SQLModel · SQLite (`nextowner.db`) → Postgres later · JWT auth (bcrypt) · WebSockets for chat · pytest / Vitest / Playwright. All third-party vendors (Stripe, Persona, Escrow.com) are **mocked locally**. 100% local — no cloud, no Docker. Node 20+, Python 3.12+.

## Conventions (constitution Article 4)

- **`/api` prefix in all code** (WebSockets under `/ws`); local Vite dev-proxy forwards both to FastAPI — no CORS. Doc prose omits `/api` for readability; **code and tests always include it**.
- Product name is **NextOwner** in all user-facing strings, `FastAPI(title="NextOwner API")`, and the SQLite file `nextowner.db`.
- REST: plural nouns (`/listings`), sub-resources for ownership (`/listings/{id}/private`), POST verbs for state transitions (`/offers/{id}/accept`).
- Error codes: `401` unauthenticated, `403` forbidden, `404` not found, **`409` invalid state transition**, `422` validation.

## Commands (`npm test` works since M0; per-file examples exist from their milestones)

```bash
npm test                                    # full suite (backend pytest + frontend vitest) — the DoD gate
cd backend && pytest -q                     # fast backend loop
cd backend && pytest tests/test_nda_gate.py -q   # a single file (exists from M5)
cd backend && pytest -q -x --lf             # re-run only last failures
```

Tests use fresh in-memory SQLite per test via `dependency_overrides`; they go through the real endpoints except for seeding (making admin, force-setting status). See `docs/testing_guide.md`.

**Windows dev machine:** activate the backend venv with `.venv\Scripts\activate` (PowerShell/cmd) or `source .venv/Scripts/activate` in Git Bash — the Bash tool runs Git Bash, so the Unix `.venv/bin/activate` path does not exist.

## Key references

@specs/000-constitution.md

- `docs/security.md` — **binding.** End-to-end threat model + security checklist; consult at every step (owner's #1 priority).
- `docs/design_implementation.md` — architecture (Part 2), local dev setup (§3.3–3.4), milestone build guide (Part 4). **Start here for any implementation.**
- `docs/milestones.md` — the milestone runbook + **§ Scope fold-ins** (per-milestone gap-review additions; read at spec time).
- `docs/testing_guide.md` — test framework + per-milestone test checklists (§5); tests ARE the acceptance criteria.
- `docs/acquire_design.md` — requirements FR-1…23 + NFRs (cite these in specs).
- `docs/error_handling.md` — the product's failure contract (error response shape, backend/frontend patterns, vendor failure modes); every spec gets an **Errors & failure modes** section.
- `docs/data_protection.md` — the technical privacy slice (PII inventory, data-minimization, **erasure-ready schema**, KYC-via-vendor); the legal/policy layer is deferred to `legal-compliance`.
- `docs/agentic_scope.md` — post-MVP agentic roadmap.

## Diagrams

`docs/diagrams/*.excalidraw` and `*.html` are **generated** from the `elements_*.json` sources in `docs/diagrams/diagGenerator/` — the JSON is the source of truth, and editing one output never updates the other. To change a diagram, edit its JSON and regenerate both outputs with `/gen-diagrams`.
