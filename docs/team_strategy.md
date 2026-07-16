# NextOwner — Team Strategy

> How to staff NextOwner from the start of the build (planning complete; M0 scaffold shipped) to a completed, launched, monetized product. The team is shaped by three facts about *this* product: it is a **two-sided trust marketplace** (intermediating real business sales, money, NDAs, KYC), **security is the #1 priority**, and it is built **agent-ready** on a spec-driven process. That means more weight on security, trust/ops, and marketplace growth than a typical SaaS build.

---

## The team, by function

### 1. Product & Technical Leadership

- **Product Lead / Head of Product** — *8–12 yrs, marketplace or fintech.* Owns the roadmap (the M0–M12 milestone plan and beyond), prioritizes the FR-1…23 backlog, defines the curation policy (Acquire's ~45% quality gate is the moat) and the monetization model (subscriptions + listing fees). The bridge between `requirements.md` (the FRs/NFRs) and the build.
- **Engineering Lead / Tech Lead** — *10+ yrs, full-stack.* Guardian of the "API is the only door" architecture and the spec-driven-development discipline (spec → failing tests → implement → green). Owns architectural decisions, code review, the SQLite→Postgres migration, and keeping the agent-readiness invariants intact as the code grows. **Deeply hands-on across the whole stack** — Python (FastAPI), React + JavaScript/TypeScript, full-stack integration, SQL *and* NoSQL data modeling, and system design (the strongest axis) — so no architectural call is ever made second-hand.

### 2. Core Engineering

> **Shared baseline — the Tech Lead and every engineer below are full-stack generalists**, each with real, hands-on experience across **Python, React, JavaScript/TypeScript, full-stack delivery, SQL *and* NoSQL databases, and system design**. The specialization in each title is that person's *center of gravity, not a boundary* — anyone can pick up work anywhere in the stack when it makes sense for the task. What follows is where each one leads, not the limit of what they can do.

- **Senior Backend Engineer (Python / FastAPI)** — *6–10 yrs.* The heart of the product: `permissions.py` trust boundaries, the state machines (`listing` / `offer` / `access_request`), the NDA gate, WebSocket chat, the SQLModel data model, and the mocked-vendor interfaces (Stripe / Persona / Escrow) built to production shape.
- **Senior Frontend Engineer (React / TypeScript)** — *6–10 yrs.* The Vite + MUI + MobX SPA: the multi-step seller listing wizard, marketplace browse with anonymous cards, the data-room/chat UI, admin queue, and dashboards. Owns client-side leak prevention and the JWT / `lib/api.ts` layer.
- **⭐ Application Security Engineer (AppSec)** — *8+ yrs, product security.* **The #1-priority role.** Owns `docs/security.md`, threat-models each milestone, red-teams the NDA gate (the crown jewel), hardens auth/JWT, enforces upload safety and secrets management, drives the permission-test suite, dependency/supply-chain hygiene, and deploy hardening (TLS / CSP / WAF / rate-limiting). In a marketplace where a data leak is a business-ending event, this is non-negotiable.
- **DevOps / Platform / SRE** — *6–10 yrs.* The single-origin production deploy (reverse proxy for `/api` + `/ws`), CI/CD, the Postgres migration + Alembic, backups, secrets manager, and observability (the Sentry/monitoring equivalent). Comes in as you move from local toward launch.
- **AI / ML Engineer (Agentic)** — *6–10 yrs, LLM/agents.* **Post-MVP**, for the `agentic_scope.md` layer (deal-scout, diligence agent). Builds agents that run *as scoped users through the same `permissions.py` gates*, tool-calling / MCP, evals-as-pytest, `agent_runs` tracing, and pgvector for comps/memory. The whole stack was chosen to make this person's job possible.

### 3. Design

- **Product Designer / UX** — *6–10 yrs, marketplace or SaaS.* The two-sided flows and, critically, the **trust UX** (NDA signing, access requests, the data room, verified-buyer badges) where design directly affects whether deals happen. Owns the MUI design system and conversion surfaces like the valuation-calculator lead magnet.

### 4. Quality

- **QA / SDET (Test Automation)** — *5–8 yrs.* SDD already makes tests the acceptance criteria; this role deepens the negative/permission-test coverage, builds the Playwright golden-path E2E, and adds load/perf testing. Often folded into engineering early, dedicated as you scale.

### 5. Trust, Safety, Legal & Compliance *(marketplace-specific, easy to underestimate)*

- **Trust & Safety / Marketplace Ops Lead** — *5–10 yrs.* Runs the curation queue (the quality gate that *is* the brand), fraud detection, buyer verification review, and dispute handling. The human layer behind the admin tooling.
- **Legal / Compliance Counsel** — *10+ yrs; fractional/advisory at MVP.* The NDA framework, Terms of Service, escrow/APA (asset-purchase agreements), KYC/AML for money movement, data-privacy (GDPR/CCPA), and the USPTO/trademark search the constitution flags. Almost certainly fractional early, not full-time.

### 6. Growth & Data

- **Growth / Marketing Lead** — *6–10 yrs, marketplace growth.* Solves the existential marketplace problem: **liquidity and the cold-start** (enough listings *and* enough buyers). SEO on the marketing site, category landing pages, the valuation-calculator funnel, and the saved-search/alert re-engagement loop. A technically flawless marketplace with no liquidity is dead.
- **Data Analyst** — *4–8 yrs; later.* Funnel and cohort analysis off the `track()` analytics events, listing→offer conversion, retention. ChartMogul-style metrics once there's real volume.

---

## Phased build — the roster per phase

Don't hire all ~13 at once. Sequence it:

| Phase | Focus | Add these roles |
|---|---|---|
| **1 — MVP build (M0–M12)** | Ship the core product | Product Lead, Tech Lead, 1 Backend, 1 Frontend, **AppSec**, Product Designer (QA folded into engineering) |
| **2 — Harden & launch** | Production, trust, go-live | + DevOps/SRE, Trust & Safety/Ops Lead, fractional Legal, dedicated QA/SDET |
| **3 — Scale & intelligence** | Growth + the agentic layer | + Growth Lead, AI/ML Engineer, Data Analyst |

---

## When to hire — triggers for Phase 2 and Phase 3

Hire on **signals, not the calendar.** Below are the concrete triggers that mean "it's time," tied to NextOwner's milestones and business state.

### Phase 2 — Harden & Launch

**Overall signal:** the core deal loop works end-to-end — roughly **Milestone 7 complete** (browse → NDA gate → chat → offer → accept) — and you are preparing to move off `localhost` to a real domain with real users. Bring these on as you *approach* real users, not after something breaks.

| Role | Hire when… |
|---|---|
| **DevOps / SRE** | You're ready to deploy off `localhost` — doing the SQLite→Postgres migration, standing up CI/CD + a staging environment, or the moment a second engineer needs a shared environment. Don't ship to real users without this seat filled. |
| **Trust & Safety / Ops Lead** | Real (non-seed) sellers start submitting listings and real buyers request access — i.e. **before your first genuine users**, or as soon as curation volume exceeds the handful of listings/day the founder can personally review. This is the brand's quality gate; don't let it lapse. |
| **Legal / Compliance (fractional)** | You're about to make NDAs, ToS, and money movement legally *real* — **before launch**, and definitely before the first real transaction or before swapping mocked Stripe/Persona/Escrow for live vendors. Engage fractionally the moment the NDA text stops being a placeholder. |
| **QA / SDET (dedicated)** | You enter **Phase D** (the Playwright golden-path E2E) and pre-launch hardening, or when the regression / negative-test surface grows past what the engineers can maintain comfortably alongside feature work. |

### Phase 3 — Scale & Intelligence

**Overall signal:** the product is **live, stable, and working**, and the bottleneck has shifted from "does it work?" to "can we get liquidity and make it smarter?" These are scale investments — premature hiring here burns runway before there's traction to scale.

| Role | Hire when… |
|---|---|
| **Growth / Marketing Lead** | The product is launched and functional but **starved for liquidity** (supply of listings and/or demand of buyers). Note: growth *thinking* starts earlier — SEO, category pages, and the valuation-calculator funnel are built into the MVP — but the dedicated hire pays off once there's a working product and some early traction to pour fuel on. |
| **AI / ML Engineer (Agentic)** | The core platform is stable and live, the **Postgres swap (pgvector) is done**, and you have enough real listing / deal / comps data for the `agentic_scope.md` features (deal-scout, diligence agent) and for meaningful evals. Building agents before there's data and a stable permission surface is wasted effort. |
| **Data Analyst** | You have **real usage volume** — enough `track()` events, users, and listing→offer flow that funnel / cohort / retention analysis is statistically meaningful (roughly: hundreds of active users and consistent weekly deal activity). Before that, the founder/PM reads the raw numbers. |

---

## Lean-start reality

At MVP scale, roles double up. A strong **security-minded full-stack Tech Lead** can cover much of the backend + AppSec + DevOps early; the Product Lead often owns Trust & Safety at first; Legal and Design can be fractional. You could genuinely start the build with **4–5 people** (Tech Lead, backend, frontend, designer, and either a dedicated AppSec or a very security-literate lead) and add specialists as the risk surface grows — which, for a money-and-trust marketplace, it will.

**The one role to never under-invest in, given the stated priority: AppSec.** Everything else can flex; the trust boundary *is* the product.
