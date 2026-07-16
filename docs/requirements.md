# NextOwner — Requirements (FRs + NFRs)

> **What this is:** **NextOwner's requirements source of truth** — the MVP scope (F1–F12), the functional requirements (FR-1…FR-23), and the non-functional requirements. **Specs cite this file.** Constitution Article 3: every `spec.md` references the FRs it satisfies.
>
> **Provenance (restructured 2026-07-16).** These requirements were *derived from* the Acquire teardown and adapted for NextOwner (see FR-13's amendment note). They lived inside that teardown — `docs/acquire_design.md` — until the two jobs were separated: the research is now **[`research/acquire_design.md`](./research/acquire_design.md)** (reference, binding on nobody), and this file is the product definition (binding).
>
> **Why the split was necessary:** while the two shared a cover, an NFR here demanded scale *"without re-architecture"* while prescribing *"serverless auto-scaling (Functions/Firestore) preferred"* — the stack constitution Article 1 explicitly rejects. It was true of Acquire and read as binding on NextOwner for nine milestones. **Read this file for what NextOwner must do; read the teardown for what Acquire did.** Where a requirement below still cites Acquire, it is citing *evidence*, never an instruction.

---

## 1. MVP Feature Set (recommended subset)

Goal of the MVP: prove the core loop — **a seller can list a business, a qualified buyer can find it, they connect, and express deal intent** — without building payments-heavy or service-heavy features.

> *2026-07-16: renumbered **M1–M12 → F1–F12** (F = MVP feature) so these can't be confused with the build milestones M0–M12 in `docs/milestones.md` — "M5" used to mean browse here and the NDA gate there.*

| # | MVP feature | Source feature | Why in MVP |
|---|---|---|---|
| F1 | Email + Google auth, buyer/seller roles | 18–20 | Table stakes; Firebase Auth makes it ~free |
| F2 | Seller listing builder with structured financial fields | 1 | Core supply |
| F3 | Admin curation queue (approve/reject listing) | 5, 32 | Marketplace quality is the moat — needed day 1 |
| F4 | Anonymous public listing card + gated private details | 6, 19 | The freemium/NDA gate is the core mechanic |
| F5 | Browse + filter (type, price, revenue, profit) + keyword search | 18 | Core demand |
| F6 | Click-to-sign NDA that unlocks private details | 22 | Lightweight version of the trust gate |
| F7 | In-app buyer↔seller messaging (realtime) | 10, 25 | The "connection" moment — the marketplace's job |
| F8 | Simple offer/LOI form (structured terms, accept/decline) | 11, 26 | Proves deal intent end-to-end |
| F9 | Saved search + email alerts for new listings | 23 | Retention loop for buyers |
| F10 | Watchlist/favorites | 31 | Cheap, high-engagement |
| F11 | Basic buyer verification (email + manual proof-of-funds upload) | 21 | Manual stand-in for Persona |
| F12 | Rule-of-thumb valuation calculator (multiple × revenue/profit) | 2 | Great lead magnet, simple to build |

**Deliberately excluded from MVP** (add post-validation): Stripe subscriptions & paywall (F4 can be a manual gate first), Persona KYC, escrow integration, APA generation, metrics-sync integrations (ChartMogul etc.), financing, advisor programs, Academy, Slack alerts, session replay, referral program.

---

## 2. Functional Requirements

### Auth & profiles
- **FR-1** Users can register/sign in with email-password and Google OAuth; sessions use short-lived tokens with refresh.
- **FR-2** A user selects a role (buyer / seller); a user may hold both roles under one account.
- **FR-3** Buyers complete a profile: acquisition budget, target industries, experience, optional proof of funds.
- **FR-4** Sellers can verify identity/business before listing goes live (MVP: manual review; scale: Persona-style KYC).

### Listings (supply)
- **FR-5** Sellers create listings with: business type, description, founding year, TTM revenue & profit, MRR/ARR, churn, team size, tech stack, reason for sale, asking price.
- **FR-6** Listings are anonymous publicly; identifying details (name, URL, financial statements) are hidden until NDA acceptance.
- **FR-7** Listings enter a **pending-review** state; an admin approves, rejects (with reason), or requests changes before publication.
- **FR-8** Sellers can edit, pause, mark under-offer, or close listings; state changes propagate to search and alerts.
- **FR-9** Sellers can upload supporting documents (P&L, metrics screenshots) stored privately.

### Discovery (demand)
- **FR-10** Buyers can browse, keyword-search, filter (type, price range, revenue, profit, multiple) and sort listings.
- **FR-11** Buyers can save a search; new matching listings trigger an email (and later Slack/in-app) alert within N minutes of publication.
- **FR-12** Buyers can favorite listings into a watchlist.

### Access, NDA & deal flow
- **FR-13** A buyer signs the standardized platform NDA once (click-wrap, timestamped on their account); thereafter they request access per listing, each request timestamped per buyer-listing pair. *(Amended 2026-07-13: platform-wide NDA adopted from Baton research; Acquire itself uses per-listing auto-signed NDAs.)*
- **FR-14** Sellers can approve/deny access requests and see buyer profile/verification status before approving.
- **FR-15** Upon access, buyer sees full financials, documents, and the seller's identity.
- **FR-16** Buyer and seller can exchange realtime messages with unread counts and email fallback notifications.
- **FR-17** Buyers can submit a structured offer/LOI (price, structure, contingencies, close date); sellers can accept, decline, or counter; both parties see offer history.
- **FR-18** (Post-MVP) Accepted offers create a **deal room**: APA drafting, checklist, escrow initiation via Escrow.com, asset-transfer tracking.

### Monetization
- **FR-19** (Post-MVP) Buyer subscription tiers gate private-detail access by deal size; billing via Stripe with self-serve upgrade/cancel.
- **FR-20** (Post-MVP) Seller listing fee billing and automated closing-fee invoicing on deal completion.

### Admin & operations
- **FR-21** Admin dashboard: curation queue, user management, listing/report moderation, deal monitoring, metrics.
- **FR-22** All notification templates (NDA signed, new message, new offer, listing approved…) are centrally managed and event-driven.
- **FR-23** Valuation tool: public form computes an estimate from revenue/profit/growth/churn using published multiples; captures email as a lead.

## 3. Non-Functional Requirements

> **Read-me first (added 2026-07-16).** This file is a **research teardown of Acquire**, but the constitution and `CLAUDE.md` promote its FRs + NFRs to NextOwner's **requirements source of truth** ("cite these in specs"). The FRs were adapted for NextOwner as that happened (see FR-13's amendment note); **this NFR table was not** — several cells still state the requirement in *Acquire's* stack vocabulary (Firestore security rules, Cloud Functions logs, Acquire's versioned bundle tags). **Read every cell for the *requirement*, never the mechanism** — NextOwner's mechanism is constitution Article 1.
>
> **Labelling convention.** Where a cell splits its parts — as **Scalability** now does — the labels are binding: ***Target*** and ***NextOwner*** state what **NextOwner must do** (cite these); ***Acquire*** is **observed evidence about a different product — never an instruction.** The Scalability row was split because its mechanism was actively misleading: it demanded scale *"without re-architecture"* while prescribing the serverless stack Article 1 rejects — precisely the auto-scaling NextOwner does **not** get for free. The contrast is kept rather than deleted, because *why* Acquire gets it free is the lesson.
>
> **Why the other rows aren't split (and can't be, cheaply).** A mechanical Acquire/NextOwner split of the remaining rows would need fresh research, not editing: this file's method (see [`research/acquire_design.md`](./research/acquire_design.md) — marketing pages, response headers, JS bundles) **cannot observe a p95 or an uptime SLO**, so most cells are **authored requirements wearing Acquire's vocabulary**, not measured Acquire facts. Splitting them would manufacture attributions nobody verified. Scalability was separable only because its mechanism *is* directly observed ([`research/acquire_design.md`](./research/acquire_design.md) §2's stack table: Cloud Functions + Firestore, evidence "config in bundle"). The rest stay as-is pending a real pass.

| Category | Requirement |
|---|---|
| **Performance** | Listing search p95 < 500 ms; page TTI < 3 s on 4G; realtime message delivery < 1 s |
| **Scalability** | **Target *(binding)*:** support 100k+ listings and 500k+ users without re-architecture; fan-out alert jobs must handle publication spikes.<br>**Acquire *(observed — §2 stack table; not an instruction)*:** serverless auto-scaling — Cloud Functions + Firestore. The platform makes per-instance state *impossible*, so elasticity is free and "without re-architecture" is true **for them**, structurally.<br>**NextOwner *(binding)*:** long-running FastAPI processes behind a load balancer (Article 1) — **no free lunch, so: no per-instance state.** JWT auth is already stateless (the load-balancer prerequisite we have); chat fan-out, upload storage, and rate limiting are not — see `design_implementation.md` § *Horizontal scale* for the three blockers, their fixes, and the milestones that own them. |
| **Availability** | 99.9% uptime for marketplace and chat; graceful maintenance mode (Acquire ships `CheckMaintenanceMode`); health-check endpoints |
| **Security** | TLS everywhere; role- and document-level access rules (Firestore security rules); private financials never exposed pre-NDA (server-enforced, not just UI); App-Check-style bot/abuse protection; secrets in server-side config only |
| **Privacy & compliance** | GDPR/CCPA data rights; PII minimization; KYC data handled only by the verification vendor (Persona pattern); NDA records retained with timestamps; cookie-consent (TCF) — Acquire ships a `__tcfapiLocator` frame |
| **Data integrity** | Financial metrics traceable to source (synced vs. self-reported flagged distinctly); immutable audit log of offers, NDA acceptances, and listing state changes |
| **Trust & safety** | Human curation of all listings; verified-buyer badges; fraud-report workflow; rate limiting on outreach to prevent spam |
| **Observability** | Centralized error tracking (Sentry-class) with session replay; product analytics via CDP (Segment-class); structured logs for Functions; alerting on error-rate/latency SLOs |
| **Maintainability** | Feature-flag-driven releases; typed codebase; CI with automated tests on rules/functions; versioned asset deploys (Acquire tags bundles `v80.x`) |
| **Usability & accessibility** | Responsive (mobile-first browsing); WCAG 2.1 AA for core flows; empty/loading/error states for all realtime views |
| **SEO** | Marketing/category pages server-rendered or static with structured data; the gated app can stay a SPA |
| **Cost** | Serverless pay-per-use baseline; alerting on Firestore read amplification (common cost trap for marketplace feeds) |

