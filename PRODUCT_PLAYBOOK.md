# Product Playbook — From Zero to a Buildable, Secure Product (with Claude Code)

> **What this is:** a reusable, product-agnostic method for taking *any* new product idea from a blank folder to a fully planned, security-first, spec-driven build — the same way NextOwner was set up. It captures the process, not the specific product.
>
> **Two audiences:**
> 1. **A human** who wants to understand or run the method.
> 2. **Claude Code** — hand this file to Claude at the start of a new project and say *"Follow this playbook to help me build \<my idea\>."* Claude will produce the same class of artifacts (research → requirements → architecture → constitution → SDD → security → Claude Code setup).
>
> **How to read it:** each phase has a **Goal**, the **Steps** (what to do), the **Artifacts** it produces (the files), and **How Claude helps**. Do the phases roughly in order; adapt as needed. Jargon is defined the first time it appears.

---

## The philosophy (why this method works)

- **Learn from the market before building.** Real, shipped competitors are free blueprints — study them first.
- **Decide the binding rules once, up front.** A short "constitution" everyone (human and AI) follows prevents drift.
- **Tests are the specification.** Write the acceptance criteria as tests *before* the code (Spec-Driven Development).
- **Security is designed in, not bolted on.** Especially for anything touching money, private data, or trust.
- **Persist the knowledge.** Docs + a `CLAUDE.md` + skills + memory keep Claude consistent across sessions.
- **Small, verified steps.** Build in ordered milestones; commit only when tests are green; version everything.

---

## Phase 0 — Frame the idea

**Goal:** a crisp, shared understanding of *what* you're building and *why*.

**Steps:**
- Write a **one-line problem statement**: what problem, for whom.
- Name the **target users** (each distinct type — e.g., buyers, sellers, admins).
- State **why now / why you** (the wedge or differentiator, even if rough).
- Decide the **learning goal or business goal** (a portfolio/learning build and a fundable venture make different tradeoffs).
- Identify **1 reference product** you're inspired by, if any.

**Artifacts:** a short `README.md` stub (title + one-paragraph description).

**How Claude helps:** sharpen the problem statement; name the actors and the core loop.

---

## Phase 1 — Research the market

**Goal:** understand how real products in this space are built and run, so you don't reinvent (or re-break) anything.

**Steps:**
- Pick **3–5 real competitors / reference products**.
- For **each**, write a **teardown**: what it does, its likely tech stack (from public pages/bundles), its full feature list, its business model + pricing, and how it handles trust/UX.
- Write a **synthesis** across all of them: a market map, the recurring **patterns / "category laws"**, a side-by-side stack comparison, and — most importantly — **your product's "white space"** (where you differ).
- Capture a **"cool features" list**: ideas worth adopting now vs. backlog.

**Artifacts:** `docs/research/<competitor>.md` (one per competitor), `docs/research/synthesis.md`, `docs/research/cool_features.md`.

**How Claude helps:** web research, structured teardowns in a consistent template, cross-company synthesis, extracting the patterns and the white space.

---

## Phase 2 — Define the requirements

**Goal:** turn research into a concrete, testable list of what the product must do.

**Steps:**
- Write **Functional Requirements (FRs)** — numbered capabilities (`FR-1`, `FR-2`, …). Each should be specific enough to later become a test.
- Write **Non-Functional Requirements (NFRs)** — security, performance, availability, privacy/compliance, maintainability.
- Define the **MVP subset**: which FRs are in the first version, which are later. Be ruthless.

**Artifacts:** a requirements/design-research doc (e.g., `docs/<domain>_design.md`) holding the FRs + NFRs. *This becomes your "source of truth" for what to build.*

**How Claude helps:** derive FRs from the research; separate MVP from post-MVP; flag missing NFRs (especially security/privacy).

---

## Phase 3 — Choose the stack & architecture

**Goal:** decide *how* it's built, and lock the **one architectural invariant** that protects the product.

**Steps:**
- Choose the **tech stack** with **explicit rationale** tied to your goals (learning value, team skills, future needs like AI/agents, hosting constraints).
- Define the **core architecture principle(s)** — especially the **security/trust boundary**. *Example (NextOwner): "The API is the only door — the browser never touches the database; every permission check lives in one place."* Decide this **before** writing code.
- Sketch the **data model** (the main entities and their relationships) and the **key components**.
- Make **diagrams** (system architecture + the main business/workflow) — they catch gaps early.
- Decide what **third-party services** you'll need and **mock them locally** first (payments, KYC, escrow, etc.), built to production-shaped interfaces.

**Artifacts:** a design/implementation guide (e.g., `docs/design_implementation.md`) with architecture, data model, local dev setup, and a milestone build guide; diagram files.

**How Claude helps:** propose/compare stacks with tradeoffs; design the data model and the permission layer; generate diagrams; define mock interfaces.

---

## Phase 4 — Write the Constitution (binding decisions)

**Goal:** one short document that **every spec and every line of code must obey** — the anti-drift anchor.

**Steps:** capture, as binding articles:
- **Tech stack** (the decisions from Phase 3, with rationale).
- **Architecture principles** (the invariants — e.g., the trust boundary, "never trust the client," public/private data split, state machines).
- **Development process** (that you use Spec-Driven Development — Phase 5 — and the definition of done).
- **Conventions** (product name, naming, API/REST style, error codes, feature flags).
- An **amendment log** (date + reason for every change to the constitution).

**Artifacts:** `specs/000-constitution.md`.

**How Claude helps:** draft the constitution from Phases 2–3; keep it short and binding; maintain the amendment log.

---

## Phase 5 — Adopt Spec-Driven Development (SDD)

**Goal:** a disciplined build loop where **tests are the acceptance criteria**, written before the code.

**Key terms:**
- **Milestone:** a small, shippable slice of the product, built in a fixed order.
- **Spec:** user stories + **GIVEN/WHEN/THEN** acceptance scenarios + the FRs they satisfy.
- **Plan:** the schema changes, endpoints, and components a milestone touches.

**Steps:**
- Break the build into **ordered milestones**. **Milestone 0 = scaffold the project and prove the pipeline end-to-end** (e.g., a `GET /health` that works), *before* any feature.
- For each milestone, run the loop:
  1. Write `specs/NNN-name/spec.md` (stories + GIVEN/WHEN/THEN + FR refs) and `plan.md` — **before code**.
  2. Turn **every GIVEN/WHEN/THEN into exactly one test**, written to **fail first**.
  3. Implement until the tests pass.
  4. Run the **full** test suite — it must be green.
  5. **Commit only when green.** Then the next milestone.
- **Spec just-in-time:** only spec **1–2 milestones ahead**, never the whole backlog (later specs depend on what you learn building earlier ones).
- Maintain a **testing guide** with a per-milestone test checklist (each ☐ = one test).

**Artifacts:** `docs/testing_guide.md`; `specs/NNN-name/{spec.md,plan.md}` (created as you go).

**How Claude helps:** scaffold each spec+plan, write the failing tests from the checklist, implement, and gate the definition of done (see the `/new-spec` and `/dod` skills in Phase 7).

---

## Phase 6 — Make security a first-class requirement

**Goal:** for any product touching money, private data, or trust, treat security as a **top priority**, designed and tested at every step.

**Steps:**
- Write a **`docs/security.md`** covering:
  - The **end-to-end threat model** across every boundary (frontend→backend, backend→database, database→backend, backend→frontend, and realtime/WebSocket).
  - **Cross-cutting controls**: authentication, authorization (default-deny), input validation, output/leak prevention, secrets in env only, file-upload safety, dependency hygiene, webhook signature verification.
  - An **edge-case abuse checklist** (IDOR, mass-assignment, illegal state transitions, enumeration, race conditions, path traversal, token attacks, DoS).
  - A **per-milestone security focus** and a **"touched → must-cover" test matrix** (if a change touches auth/permissions/uploads/money/etc., the matching negative test must exist).
- **Weave it into SDD:** every spec gets a **"Security & abuse"** subsection; **forbidden-path tests are written first**; the definition-of-done check runs the security matrix.

**Artifacts:** `docs/security.md`, plus security subsections in every spec.

**How Claude helps:** produce the threat model tailored to your architecture; add security acceptance criteria to specs; enforce the security matrix at review.

---

## Phase 7 — Set up Claude Code for the project

**Goal:** make Claude a consistent, high-leverage teammate across sessions.

**Steps:**
- **`CLAUDE.md`** (loaded into every session): keep it **concise** — only what Claude would get wrong without it. Include: project status, the SDD loop, the non-negotiable rules, stack, conventions, key non-obvious commands, and `@`-imports/pointers to the big docs (constitution, security, testing). Cut anything Claude can discover by reading code.
- **Skills** (reusable slash-command workflows in `.claude/skills/<name>/SKILL.md`): package the repeatable steps, e.g.
  - `/new-spec <name>` — scaffold a milestone's `spec.md` + `plan.md` from the constitution + requirements.
  - `/dod` — run the tests + the security matrix; gate "definition of done."
  - `/scaffold-<first-milestone>` — the one-time project scaffold (mark it user-only if it has big side effects).
  - Any project-specific generator (e.g., a diagram or report builder).
- **Memory:** save standing directives so they persist across sessions (e.g., *"security is the #1 priority"*).
- **Version control:** `git init`, a sensible `.gitignore` (secrets, DBs, uploads, local-only files), commit-when-green, push to a remote.
- **Run `/init`** — it bootstraps `CLAUDE.md` + skills + git for you and re-scans anytime the codebase changes.

**Artifacts:** `CLAUDE.md`, `.claude/skills/*`, `.gitignore`, a git repo + remote, memory entries.

**How Claude helps:** `/init` does most of this; Claude drafts the skills and CLAUDE.md tailored to the project.

---

## Phase 8 — Plan the team (optional — for real ventures)

**Goal:** know *who* takes the product to completion and *when* to add them.

**Steps:**
- List the **team by function** (product, engineering, security, design, QA, trust/ops, legal, growth) with **seniority** and **responsibilities tied to the product's real demands**.
- Sequence hiring in **phases** with **"when-to-hire" triggers** (hire on signals — e.g., "the core loop works end-to-end," "real users arrive," "liquidity is the bottleneck" — not on the calendar).
- Note where **roles double up** at small scale, and the **one role never to under-invest in** (for a trust product: security).

**Artifacts:** `docs/team_strategy.md`.

**How Claude helps:** draft the team and phased hiring plan from the product's architecture and risk profile.

---

## Phase 9 — Build, milestone by milestone

**Goal:** ship the product using everything above.

**Steps:**
- Run **`/scaffold-<M0>`** first — real code now exists.
- For each milestone: `/new-spec` → write failing tests → implement → `/dod` → **commit + push when green**.
- **Re-run `/init` after Milestone 0**, when there's real code to document (module-specific rules, subdirectory `CLAUDE.md` files, a format-on-edit hook once linters exist).
- Keep specs **1–2 milestones ahead**; keep the full suite green; keep security tests first.

**How Claude helps:** drives the whole loop — specs, tests, implementation, security review, commits.

---

## The artifact map (what this method produces)

```
<project>/
├── README.md                      # Phase 0 — one-paragraph pitch + doc map
├── PRODUCT_PLAYBOOK.md            # this file (reuse across products)
├── CLAUDE.md                      # Phase 7 — concise persistent guidance for Claude
├── .gitignore                     # Phase 7
├── .claude/skills/               # Phase 7 — /new-spec, /dod, /scaffold-M0, generators
├── docs/
│   ├── research/                 # Phase 1 — competitor teardowns + synthesis
│   ├── <domain>_design.md        # Phase 2 — FRs + NFRs (requirements source of truth)
│   ├── design_implementation.md  # Phase 3 — architecture, data model, milestone guide
│   ├── testing_guide.md          # Phase 5 — per-milestone test checklists
│   ├── security.md               # Phase 6 — threat model + security matrix
│   ├── team_strategy.md          # Phase 8 — team + phased hiring (optional)
│   └── diagrams/                 # Phase 3 — architecture + workflow diagrams
├── specs/
│   └── 000-constitution.md       # Phase 4 — binding decisions
│       └── NNN-name/{spec.md,plan.md}   # Phase 5 — created per milestone, just-in-time
└── app/ · backend/ · seed/       # Phase 9 — created at Milestone 0
```

---

## Reuse it — the kickoff prompt to give Claude

Paste this to Claude Code in a fresh project folder, with this file present:

> *"I want to build **\<one-line product idea, target users\>**. Follow `PRODUCT_PLAYBOOK.md` in this folder. Start at **Phase 0** and work forward, pausing for my input at each phase. Research **\<any competitors I name, or find good ones\>**. My priorities are **\<e.g., security-first, learning value, speed\>**. Set up Claude Code (CLAUDE.md + skills + git) once the planning docs exist, then we'll build milestone by milestone."*

Claude will then reproduce this method for the new product: research → requirements → architecture → constitution → SDD + testing guide → security → Claude Code setup → (optional) team plan → build.

---

## One-screen checklist

- [ ] **P0** Frame: problem, users, goal, reference product → `README.md` stub
- [ ] **P1** Research 3–5 competitors + synthesis + white space → `docs/research/`
- [ ] **P2** FRs + NFRs + MVP subset → `docs/<domain>_design.md`
- [ ] **P3** Stack + architecture invariant + data model + diagrams + mocked vendors → `docs/design_implementation.md`
- [ ] **P4** Constitution (binding decisions + amendment log) → `specs/000-constitution.md`
- [ ] **P5** Milestones + SDD loop + testing guide (tests fail first; commit when green) → `docs/testing_guide.md`
- [ ] **P6** Threat model + security-in-every-spec + must-cover matrix → `docs/security.md`
- [ ] **P7** CLAUDE.md + skills + git + memory (run `/init`)
- [ ] **P8** Team + phased hiring triggers (optional) → `docs/team_strategy.md`
- [ ] **P9** Scaffold M0 → build each milestone → commit + push green → re-run `/init`

---

*Golden rules, condensed: research first · decide invariants once · tests before code · security by design · commit only when green · keep Claude's context in `CLAUDE.md`, skills, and memory.*
