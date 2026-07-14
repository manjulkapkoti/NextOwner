# Q&A Notes — Milestones as Phases & Spec-Driven Development

> Captured from the working session on 13 July 2026. Relates to Part 4 of [`design_implementation.md`](./design_implementation.md).

---

## Q1: Is the Part 4 build guide (milestone by milestone) a step-by-step implementation of my web application? Can I consider them as different phases of implementation?

Yes — with one clarification about what "step-by-step" means.

**They are a genuine implementation sequence.** The ordering is dependency-driven, so you can follow it literally: auth must exist before anyone can create a listing (M1→M2), listings must exist before an admin can curate them (M2→M3), only curated listings can be browsed (M3→M4), the NDA gate needs browseable listings (M4→M5), chat only starts after access approval (M5→M6), and offers presume chat/access (M6→M7). Skipping ahead breaks things; following the order never leaves you blocked.

**They are phases, but agile-style, not waterfall-style.** Each milestone is a *vertical slice* — a bit of UI + data model + rules/functions that ends in something clickable and testable. So the right way to treat them: define "done" for a milestone, verify it works (e.g., for M5, actually confirm in the Rules Playground that a non-approved buyer is denied), then move on. Don't treat them like waterfall phases where you design everything first and integrate at the end — the value is that after every milestone you have a working, demoable app that just does more than before.

**What they are not:** a keystroke-level tutorial. Each milestone tells you *what* to build, *which* collections/tables and functions it touches, and *why* it matters to the business — but within a milestone you still write the components, choose exact field names, and design the UI yourself. That's intentional for a learning project; the doc is the map, not the turn-by-turn navigation.

One useful mental grouping for fewer, bigger phases:

| Phase | Milestones | You've built… |
|---|---|---|
| A — Foundation | M0–M1 | running stack + login/roles |
| B — Supply | M2–M3 | sellers can list, admin curates |
| C — Demand & trust | M4–M5 | buyers browse, NDA gate works (the core of the product) |
| D — Transaction | M6–M7 | chat + offers — the full deal loop, MVP is essentially done here |
| E — Retention & polish | M8–M11 | alerts, watchlist, verification, valuation tool |

After Phase D you have a demonstrable end-to-end marketplace; Phase E items are independent of each other and can be done in any order.

---

## Q2: I am planning to do spec-driven development. How does that come into the picture with these milestone-by-milestone steps?

Spec-driven development (SDD) fits this plan almost perfectly, because the existing documents form the top half of a spec hierarchy — what's missing is only the per-milestone layer.

**What already exists, in SDD terms:**

- `acquire_design.md` = the **product spec** — especially the FR-1…FR-23 functional requirements and the NFR table. These are the requirements source of truth.
- `design_implementation.md` Parts 2–3 (or Part 6 for Supabase) = the **system design spec** — architecture, data model, security model.
- Part 4's milestones = the **backlog with sequencing**. Each milestone is exactly the right size to become one feature spec.

**What SDD adds:** instead of jumping from "Milestone 5: NDA gate" straight into code, each milestone gets its own short spec *written before implementation*, and the milestone is only "done" when the implementation satisfies the spec — not when the code feels finished. The workflow per milestone becomes:

```
pick milestone → write spec.md → write plan.md → break into tasks →
implement (great fit for Claude Code) → verify against acceptance criteria → next milestone
```

A concrete structure that maps 1:1 onto the milestones:

```
specs/
├── 000-constitution.md        # decisions that bind ALL specs: Firebase vs Supabase,
│                              # naming conventions, "privileged logic only in functions", etc.
├── 001-auth-roles/            # ← Milestone 1
│   ├── spec.md                # user stories + acceptance criteria + FR references
│   ├── plan.md                # schema deltas, functions, components touched
│   └── tasks.md               # implementation checklist
├── 002-listing-builder/       # ← Milestone 2
├── 003-curation/              # ← Milestone 3
└── ...
```

**Three things make this pairing work especially well here:**

1. **Traceability is already free.** Each milestone spec just references the FRs it implements — Milestone 5's spec cites FR-13/14/15, Milestone 7 cites FR-17. When all FRs are covered by a passing spec, the MVP is done by definition, not by feeling.

2. **The data model becomes a contracted artifact.** The schema in Part 3.5/6.3 is the shared contract; each spec's `plan.md` declares its *delta* ("adds `accessRequests` collection, adds `nda gate` rule"). This prevents the classic solo-dev drift where the database quietly diverges from the docs.

3. **The security rules make specs executable.** Acceptance criteria like "GIVEN buyer with no approved access request WHEN reading `listing_private` THEN denied" translate directly into emulator rules tests (or RLS tests in Supabase). That's the SDD ideal — the spec literally runs. For example, Milestone 5's spec would be ~15 lines: three user stories, five given/when/then criteria, FR references, and out-of-scope notes ("no email notification yet — that's spec 008").

**How the phases map:** the A–E phase grouping from Q1 becomes the spec roadmap — spec and build Phase A first, and *don't* write detailed specs for Phase E up front. Spec just-in-time, one or two milestones ahead; specs written months before implementation rot just like code comments.

**One caution:** keep the constitution decision (Firebase vs. Supabase) as spec 000 and make it first — every later spec's `plan.md` depends on it, and it's the one decision that's expensive to reverse mid-way.
