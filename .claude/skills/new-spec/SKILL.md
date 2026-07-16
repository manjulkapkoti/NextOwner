---
name: new-spec
description: Scaffold a new milestone spec folder (specs/NNN-name/spec.md + plan.md) following the constitution's Spec-Driven Development rules. Use when starting a new milestone, before writing any code. Takes the milestone slug as an argument, e.g. /new-spec auth-roles.
---

# Scaffold a new milestone spec

Create `specs/NNN-<name>/spec.md` and `specs/NNN-<name>/plan.md` for the milestone named in `$ARGUMENTS`. This is the **first step of every milestone** — specs come before tests, tests come before code (constitution Article 3).

## Steps

1. **Read the ground truth first** (do not invent requirements):
   - `specs/000-constitution.md` — the binding rules every spec must comply with.
   - `docs/design_implementation.md` Part 4 — find the matching milestone's scope.
   - `docs/milestones.md` — this milestone's table row **and its § Scope fold-ins entry** (gap-review additions that must become acceptance criteria in this spec).
   - `docs/testing_guide.md` §5 — the milestone's test checklist (each ☐ becomes a GIVEN/WHEN/THEN).
   - `docs/acquire_design.md` — the FR-1…23 numbers to cite.
   - `docs/security.md` §7 + §6 — this milestone's security focus + edge cases (for the **Security & abuse** section).
   - `docs/error_handling.md` — the failure contract + this milestone's error/failure paths (for the **Errors & failure modes** section).
   - `docs/data_protection.md` — if this milestone adds a PII field or a person-referencing table (record its erasure/anonymization behavior in `plan.md`).

2. **Pick the number `NNN`.** Scan `specs/` for the highest existing `NNN-*` folder and add 1 (constitution: `000` is the constitution, `001+` follow milestone build order). Zero-pad to 3 digits. If `$ARGUMENTS` is empty, ask which milestone.

3. **Create `specs/NNN-<name>/spec.md`** with this structure:
   - **Milestone** — name + link to its section in `docs/design_implementation.md` Part 4.
   - **FR references** — the FR-N items from `docs/acquire_design.md` this milestone satisfies.
   - **User stories** — "As a <role>, I want <capability>, so that <value>."
   - **Acceptance criteria** — numbered GIVEN/WHEN/THEN scenarios. Cover happy paths **and** the forbidden paths (wrong identity → 403/404, invalid transition → 409, bad input → 422). **Each scenario must map to exactly one test** — if you can't phrase it as a testable scenario, it's too vague. Derive these from the testing_guide §5 checklist for this milestone.
   - **Security & abuse** — a dedicated subsection (security is the owner's #1 priority). Pull this milestone's row from `docs/security.md` §7 plus the relevant §6 edge cases, and write each as a forbidden-path GIVEN/WHEN/THEN (IDOR, mass-assignment, path traversal, spoofed identity, schema-leak, illegal transition, revocation). These are permission tests — the crown jewels.
   - **Errors & failure modes** — a dedicated subsection (`docs/error_handling.md`). Enumerate this milestone's failure paths as GIVEN/WHEN/THEN → one test each: input **validation** (422, field-level), **illegal state transitions** (409), and a **500-safety** case (a forced error returns the generic contract — no stack/SQL leak). For UI work, add the **error/empty/loading** states and inline 422 display. Note any **mocked-vendor failure** states (decline / KYC-fail / dispute) this milestone touches.
   - **Out of scope** — what this milestone deliberately defers.

4. **Create `specs/NNN-<name>/plan.md`** with:
   - **Schema deltas** — new/changed SQLModel tables or columns (`backend/app/models.py`).
   - **Endpoints** — method + path (always with the `/api` prefix in code), the permission dependency each uses, and the status transition it performs.
   - **Permission gates** — which `permissions.py` function guards each privileged route (one function per trust boundary).
   - **Frontend** — pages/components/MobX stores touched (`app/src/`).
   - **Response models** — note any public model that must exclude identity fields by schema.
   - **Errors** — the `AppError` subclasses / machine `code`s this milestone raises (`docs/error_handling.md`), plus the frontend error/empty/loading states and any `ApiError` handling touched.
   - **Analytics events** — the `track(event, props)` events this milestone emits (event names + props; **never** private/identity fields — `docs/security.md` § Audit & logging).
   - **Data protection** — any new PII fields (justified, minimized, kept off public schemas) and the **erasure/anonymization behavior** of new person-referencing tables (`docs/data_protection.md`). The `user` table (M1) ships erasure-ready.

5. **Comply with the constitution as you write:** never trust the client for `owner_id`/`sender_id`/`status`/prices; clients never set status directly; public vs private tables stay split; use the correct error codes (401/403/404/409/422) surfaced through the `docs/error_handling.md` contract (generic messages, machine `code`, no leaks).

6. Tell the user the next step: **write the failing tests** from these acceptance criteria (`docs/testing_guide.md`), then implement.

Do not write implementation code in this skill — only the spec and plan.
