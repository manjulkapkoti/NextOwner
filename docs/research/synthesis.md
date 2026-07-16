# Competitive Research Synthesis — Four Companies, One Market

> Date: **13 July 2026**. Inputs: [`acquire_design.md`](./acquire_design.md) · [`baton_design.md`](./baton_design.md) · [`exitwise_design.md`](./exitwise_design.md) · [`littleexits_design.md`](./littleexits_design.md) · [`cool_features.md`](./cool_features.md).
> Purpose: what the four teardowns mean **together** — the category's rules, where NextOwner sits, and what it changed in our plan.

---

## 1. The Market Map

The four companies aren't really competitors — they're the same business at four deal sizes, and lining them up reveals the category's core law:

| | **Little Exits** | **Acquire.com** | **Baton** | **Exitwise** |
|---|---|---|---|---|
| Deal size | < $100k | $10k – $5M+ | $100k – $10M (main street) | $1M – $100M+ |
| Inventory | Side projects, micro-SaaS | Online businesses | Offline SMBs (bakeries, HVAC…) | Any company hiring bankers |
| Model | Self-serve marketplace | Self-serve marketplace + advisory tier | Tech-enabled **brokerage** | Pure **advisory** matchmaking |
| Humans per deal | ~0 | ~0 (optional tier) | Advisor in every deal | Bankers + attorneys run the deal |
| Software's job | IS the product | IS the product | Half the product | Lead-gen funnel |
| Team/scale signal | Solo-founder scale | 500k+ users, $500M+ closed | $15M raised, 70% close claim | ~100-founder network, $4B+ guided |

**The law: software's share of the work shrinks as deal size grows** — because at higher stakes, buyers and sellers pay for judgment and hand-holding, not tools. Every company's product decisions follow from where they sit on this curve.

**NextOwner sits in the Little Exits ↔ Acquire band** — self-serve, software-is-the-product, small online businesses. That placement is now *evidence-based*: Little Exits proves the exact MVP scope operates as a real business at solo-team scale, and Acquire proves the growth ceiling is high.

---

## 2. Seven Laws of the Category

Patterns every company follows regardless of deal size — treat these as requirements, not inspiration.

1. **Verification is the product.** Acquire syncs metrics from ChartMogul/Stripe; Baton reconciles financials *before* listing; Little Exits leads with "verified projects"; Exitwise vets its banker network. Nobody sells listings — everybody sells *believable* listings. → NextOwner: M3 curation is the moat; agentic Trust & Vetting (proposal D) is its scaling path.
2. **Anonymity + gated access is the universal trust mechanic.** Public teaser, private data room, explicit unlock everywhere. → NextOwner: the public/private table split + `require_private_access` (constitution Art. 2) is the category standard, correctly placed at the heart of the design.
3. **Gate the connection, not the browsing.** Acquire Premium ($390/yr), Little Exits Premium ($249/yr), Baton's NDA-gated engagement, Exitwise's booked call — monetization always sits on the *contact* moment. → NextOwner: FR-19's post-MVP paywall placement is confirmed three times over.
4. **The valuation calculator is the universal lead magnet.** All four ship one; Exitwise even built its only custom software for it. → NextOwner: M11 is correctly scoped; surround it with intent-based SEO content later.
5. **Human help is the upsell everywhere.** Guided by Acquire, Baton's whole company, Little Exits' `/broker`, Exitwise's entire model. Self-serve platforms grow a services tier; services companies grow software. The two ends converge. → NextOwner: keep self-serve MVP; a "guided" tier is the proven expansion slot.
6. **Success-fee economics rule the roadmap.** Revenue recognizes at close, so *close rate* and *time-to-close* are the metrics every feature must serve (Baton's 70%-close claim is their entire pitch). → NextOwner: deal-velocity features (chat, offers, deal room, orchestrator agent) deserve priority over vanity breadth.
7. **Content compounds.** Acquire's SEO category pages, Baton's changelog + engineering blog, Exitwise's valuation-query factory, Little Exits' free mini-apps — every player runs an owned-audience engine feeding the funnel. → NextOwner: post-MVP marketing playbook is already written by the market (E1–E5, L1 in `cool_features.md`).

---

## 3. Tech-Stack Synthesis

| | Frontend | Backend | Auth | Notable |
|---|---|---|---|---|
| Acquire | React SPA (Vite), MobX, MUI | **Firebase BaaS** (Firestore, Functions) | Firebase Auth | Persona KYC, Escrow.com, metrics sync |
| Little Exits | Next.js ×2 (Vercel) | **Firebase BaaS** (RTDB) | Firebase Auth | Stripe, reCAPTCHA Enterprise |
| Baton | Next.js (marketing) + Remix (app) | **Custom on AWS**, GraphQL | SuperTokens (open source) | Contentful CMS, LaunchDarkly, Elena AI |
| Exitwise | Webflow (no-code) + one Next.js micro-app | none (service business) | none | Tally, Calendly, Beehiiv |

Takeaways for NextOwner:

- **BaaS dominates at self-serve scale** (2 of 2 self-serve marketplaces run Firebase). The FastAPI choice remains a *deliberate learning + agent-readiness trade-off*, not the market default — exactly as recorded in constitution Article 1's "considered and rejected."
- **Nobody in the category runs Python.** That's not a warning — it's the bet: the agentic layer (`agentic_scope.md`) lives in Python, and NextOwner's backend will be the same language as its future agents. Baton, with a TS stack, still shipped Elena — imagine the friction NextOwner avoids.
- **Path-based single-origin zones validated twice** (Baton's `/market/*`, Exitwise's `/valuation-calculator`) — adopted in §3.4.
- **Frontend is a solved problem:** everyone is on the React family; no differentiation lives there. Spend the innovation budget on trust machinery and AI.

---

## 4. Decisions Ledger — What the Research Actually Changed

| Decision | Source | Where it landed |
|---|---|---|
| **One platform-wide NDA** + per-listing access approval | Baton | M5, FR-13, constitution Art. 4, testing_guide M5 |
| **Single-origin `/api` layout** + Vite dev proxy | Baton (+ Exitwise confirmation) | §3.4, constitution Art. 4 |
| Owner walkthrough video field | Baton | Recommended for M2 (not yet adopted) |
| Everything else | all four | Validations or post-MVP backlog (`cool_features.md`) — **zero architecture changes**, which is itself the finding: the plan survived four teardowns intact |

---

## 5. NextOwner's White Space

The research says the crowded parts are: micro self-serve (Little Exits), digital-SMB self-serve (Acquire), brokerage-hybrid (Baton), advisory (Exitwise). The **uncrowded part is intelligence**:

- Exactly **one shipped AI feature** exists across all four companies — Baton's Elena (data-room Q&A with citations). It validates the direction and sets the bar: grounded, citation-first, buyer-facing.
- Nobody has shipped the *rest* of `agentic_scope.md`: deal-scout agents, seller listing copilots, automated vetting, deal-room orchestration, comps-driven valuation from proprietary sales data (which Little Exits and Baton both gesture at but haven't productized as AI).
- NextOwner's structural advantages for that bet: Python backend (agents are native citizens), the API-is-the-only-door design (every capability is already a callable tool), and state machines as data (agents can read and advance deals safely).

Positioning in one sentence: **the self-serve marketplace where an AI analyst team comes with every deal** — Little Exits' scope, Acquire's mechanics, Elena's intelligence applied end-to-end.

---

## 6. Consolidated Post-MVP Backlog (sequenced)

From `cool_features.md`, ordered by when they become buildable:

1. **Right after Phase D** (needs a working deal loop): invoice on offer-accept (L2) · asset-transfer checklist as state machine (L3) · owner video field (B4)
2. **Growth phase** (needs traffic): valuation calculator + SEO content factory (E4, law #4) · seller-readiness quiz (E3) · newsletter (E-pattern) · free mini-tools (L1)
3. **Scale phase** (needs deals closed): "Sold on NextOwner" success-story directory (E1) · off-market profiles (B2) · comps-based valuation (L4) · guided/broker tier (law #5)
4. **The bet** (needs data + guardrails): Elena-class data-room analyst with citations (B1) → then the full `agentic_scope.md` roadmap

---

## 7. Risks the Research Surfaced

1. **Supply cold-start is the real boss fight.** Every player fights for sellers, not buyers (Baton built off-market profiles for it; Exitwise built a founder network; Acquire spends on curation marketing). NextOwner's mitigations live in phase 2–3 backlog (readiness quiz, mini-tools, success stories) — but the MVP demo needs seeded listings from day one (`seed/` is not optional polish).
2. **Trust without a brand.** All four lean on verification *and* social proof (stats, testimonials, founder networks). A new marketplace has neither — expect the curation bar (M3) and verified-buyer signals (M10) to matter more than features early on.
3. **Escrow economics at small deal sizes.** Escrow.com works for Acquire's deal band; Little Exits had to bring payments in-platform via Stripe. NextOwner's mocked escrow should eventually resolve to the Stripe-style in-platform pattern for small deals, not Escrow.com.
4. **Curation is labor.** The ~45% pass rate at Acquire implies real human review time per listing. Fine solo at MVP volume; the agentic vetting assistant (proposal D) is the documented escape hatch — budget for it before volume arrives.

---

*Research series complete: 4 companies, 3 architectures, 2 adopted decisions, 1 validated plan.*
