# Agentic Enhancements for NextOwner (an online M&A marketplace)

> Companion to [`requirements.md`](./requirements.md) (the FRs/NFRs) and [`design_implementation.md`](./design_implementation.md) (the architecture). This document proposes how **agentic AI** — LLM-driven systems that plan, use tools, iterate, and act toward a goal with humans approving the consequential steps — can be layered onto the marketplace design to improve the business, not just decorate it with chat.

---

## 1. Why agents fit this business

An M&A marketplace's economics reduce to three levers:

1. **Liquidity** — more qualified matches between buyers and listings (drives GMV).
2. **Velocity** — time from listing → close (Acquire markets "90 days"; every week cut compounds GMV per year and seller NPS).
3. **Trust** — verified data and safe transactions (drives take-rate defensibility and pricing power).

Every one of those levers is bottlenecked today by **human, document-heavy, multi-step workflows**: curation reviews, financial verification, due diligence, legal drafting, deal-room chasing. These are precisely the workloads agentic systems are good at — long-running, tool-using, checklist-driven processes with a human sign-off at the end. Acquire itself already advertises "AI-powered legal, diligence, and closing tools" in its Premium plan, confirming the direction; the proposals below go further to *agentic* (multi-step, autonomous-with-approval) capabilities.

**Real-world anchors for each pattern:** contract-review agents (Harvey, Robin AI in legal), diligence copilots in private equity (Hebbia, AlphaSense), agentic underwriting in fintech (Casca for SBA loans), fraud/vetting automation in marketplaces (Airbnb/Stripe Radar-style risk pipelines), and support agents with tool access (Intercom Fin, Decagon).

---

## 2. Proposed agentic features

Ranked roughly by business impact ÷ effort. Each lists: what it does, how it works, and the business case.

### A. Deal-Scout Agent (buyer side) — *flagship*
- **What:** A buyer states an acquisition thesis in natural language ("profitable B2B SaaS, $10–40k MRR, churn < 3%, no services revenue, transferable without founder"). The agent continuously watches new listings, scores them against the thesis with reasons ("matches 8/10 criteria; churn unverifiable — ask seller"), drafts the intro message/NDA request, and queues it for one-click approval.
- **How:** Embedding-based retrieval over listing corpus + LLM scoring pass with structured rubric output; runs as a scheduled/event-driven agent on new-listing events; memory of buyer feedback ("rejected: too much services revenue") refines future scoring.
- **Business case:** Converts passive browsing into active pipeline. Raises Premium/Platinum conversion and retention (the subscription now buys an analyst, not just a paywall). Directly increases seller-side offer counts — the metric Acquire already brags about (~10 offers/listing).

### B. Listing Copilot (seller side)
- **What:** Interviews the seller conversationally, connects to their real systems (Stripe, ChartMogul, GA4), drafts the entire listing (narrative, standardized P&L, recast financials, growth story), flags gaps a buyer will ask about, and pre-answers the curation checklist. Also auto-redacts identifying details for the anonymous public card.
- **How:** Tool-using agent with OAuth connectors (the ChartMogul/Metricable sync already exists in Acquire's design — expose it to the agent as tools); document generation with the platform's listing schema as structured output; a redaction pass with a second-model check.
- **Business case:** Cuts listing creation from days to under an hour; raises curation pass-rate (~45% today — better-prepared listings mean more sellable supply); reduces curation-team load per listing.

### C. Due-Diligence Agent (buyer side, premium add-on)
- **What:** After NDA, the buyer's agent ingests the data room (P&L, metrics exports, contracts, cap table) and produces a diligence report: revenue quality, metric anomalies (MRR vs. bank deposits mismatch, churn cohort inconsistencies), customer concentration, contract red flags (assignment clauses, change-of-control), plus a question list for the seller. For SaaS deals, optionally reviews the codebase/infra via read-only repo access.
- **How:** RAG over deal-room documents; specialized sub-agents (financial forensics, legal clause extraction, code review) fanned out by an orchestrator; every claim linked to its source document; human advisor reviews before delivery.
- **Business case:** Diligence is the #1 stall point between LOI and close — this compresses deal velocity and reduces fall-through. Naturally priced as a per-deal fee or Platinum perk (services revenue without hiring analysts).

### D. Trust & Vetting Agent (platform side)
- **What:** First-pass reviewer for every submitted listing: cross-checks claimed metrics against synced data, verifies domain ownership/traffic claims, screens seller identity signals, detects duplicate/recycled listings and AI-fabricated financials, and drafts an approve/reject recommendation with evidence for the human curator.
- **How:** Deterministic checks (data reconciliation) + LLM judgment on narrative consistency; outputs a risk score + rationale into the existing curation queue; curator remains the decision-maker.
- **Business case:** Curation is the quality moat but also the scaling bottleneck. An agent that clears the easy 70% lets the same team handle 3–5× listing volume without diluting quality — supply growth without headcount.

### E. Deal-Room Orchestrator (both sides)
- **What:** Once an LOI is accepted, an agent owns the closing checklist: generates the APA draft from accepted terms, chases missing documents from the right party ("waiting on seller's Stripe transfer confirmation — reminded 2h ago"), schedules calls, initiates escrow at the right milestone, and tracks asset transfer (domain, repo, contracts) to completion.
- **How:** Long-running stateful agent per deal; tools = document builder, e-signature, Escrow.com API, email/chat notifications, calendar; strict human approval on anything binding (sending APA, releasing escrow).
- **Business case:** Directly attacks time-to-close. Faster closes = faster success-fee recognition, higher close rate (deals die of staleness), and a wow experience both sides tell other founders about.

### F. Valuation & Negotiation Assistant
- **What:** Upgrades the static valuation calculator into an agent that pulls real comps from the platform's own closed-deal corpus ("similar SaaS at your churn/growth closed at 3.1–3.8× TTM profit in the last 12 months"), explains drivers, and — during negotiation — benchmarks offer terms (multiple, cash vs. earn-out, transition period) for either side.
- **How:** RAG over anonymized historical deal data (a proprietary data asset no competitor has at Acquire's scale) + structured comp retrieval; guardrail: outputs framed as "market data," never as advice/appraisal.
- **Business case:** Better-priced listings sell faster; the proprietary comp corpus becomes a defensible data moat and an SEO/lead-gen magnet.

### G. Financing Agent (buyer side)
- **What:** Pre-qualifies a buyer's target deal across SBA and alternative lenders: assembles the financial package from deal-room data, matches lender criteria, drafts applications, and tracks status.
- **How:** Tool-using agent over lender-partner APIs/forms; mirrors real-world agentic SBA underwriting (e.g., Casca) from the borrower side.
- **Business case:** Financing failure kills large deals; expanding the pool of *funded* buyers raises close rates on >$500k listings — where Acquire's 6% fee earns the most. Referral fees add a revenue line.

### H. Concierge Support Agent
- **What:** Replaces the static help center for logged-in users: answers "what happens after my LOI is accepted?" with awareness of *their* deal state, executes routine actions (resend NDA, update alert criteria), and escalates to humans with full context.
- **How:** RAG over help content + read-tools over the user's own deal objects + a small set of safe write-tools; standard Fin/Decagon pattern.
- **Business case:** 24/7 support is already a marketing promise — an agent makes it economically true and lifts activation for the 500k-user long tail no CSM can cover.

---

## 3. Reference agentic architecture

Add one new layer to the existing serverless design — don't rebuild it:

```
            React SPA (existing)
                 |  (new: agent chat/approval UI, run status)
                 v
   +----------------------------------------------+
   |         AGENT ORCHESTRATION LAYER (new)      |
   |  Orchestrator (owned loop or a framework)    |
   |   - per-workflow agents: scout, copilot,     |
   |     diligence, vetting, deal-room, support   |
   |   - run state + memory (Postgres · Qdrant)   |
   |   - human-in-the-loop approval gates         |
   |   - eval suite + tracing + cost metering     |
   +----------------------------------------------+
        |  tool calls (MCP servers / function calling)
        v
   Existing assets become TOOLS:
     Postgres (listings, deals)    uploads/ folder (data rooms)
     Stripe · ChartMogul · GA4     Escrow.com · e-signature
     Notification engine           Qdrant index over listings,
                                   docs & closed-deal comps (local embeddings)
```

**Design principles**

1. **Tools-first:** the platform's existing integrations (metrics sync, escrow, Stripe, notifications) are wrapped as typed tools (MCP servers fit naturally); agents get capability without new data silos.
2. **Human-in-the-loop by risk tier:** read/analyze → autonomous; outbound messages/drafts → one-click approval; anything binding (offers, APA, escrow release, listing rejection) → explicit human action. Log every step.
3. **Structured outputs everywhere:** rubrics, risk scores, and reports as JSON validated against schemas — the UI renders them, humans audit them.
4. **Grounding + citations:** diligence and valuation claims must cite the source document/metric; unverifiable claims are labeled, not smoothed over.
5. **Evals before autonomy:** each agent ships with a golden-set eval (e.g., curation agent scored against historical accept/reject decisions) and expands autonomy only as measured accuracy allows.
6. **Model & stack strategy (provider-agnostic, behind swappable interfaces):** a **local / open-source model** for agentic reasoning by default — frontier stays a drop-in swap; a **local embedding model** for matching; vectors in **local Qdrant** (a *rebuildable* index — Postgres stays the source of truth) behind a `VectorStore` interface, so pgvector remains an option. The orchestration loop is an **owned thin loop *or* a framework — decided at build time**; non-negotiable regardless: agents run as scoped users through the gates, and tools stay plain functions / MCP.

**Cross-cutting risks & guardrails**

- **Liability:** valuation/legal outputs are decision support, not advice — disclaimers plus mandatory human review on anything a party could rely on in a dispute.
- **Confidentiality:** deal-room data is NDA-bound; per-deal isolation of retrieval indexes; no cross-deal leakage in prompts or memory; vendor agreements with zero-retention inference.
- **Adversarial input:** sellers will optimize listings *for the vetting agent*, and data rooms can contain prompt-injection text; treat all document content as untrusted input, separate instructions from data, and keep deterministic reconciliation checks that an LLM cannot be talked out of.
- **Cost control:** meter tokens per run; cap autonomous loops; batch feed-scale scoring.

---

## 4. Phased roadmap

| Phase | Ship | Rationale |
|---|---|---|
| **1 — Assist (0–3 mo)** | Listing Copilot (B), Concierge agent (H), valuation upgrade (F-lite) | Single-turn/tool-light, low risk, immediate UX lift; builds the tool layer and eval habit |
| **2 — Match & vet (3–6 mo)** | Deal-Scout (A), Trust & Vetting agent (D) | Needs vector index + event-driven runs; attacks liquidity and the curation bottleneck |
| **3 — Transact (6–12 mo)** | Due-Diligence agent (C), Deal-Room Orchestrator (E) | Highest value, highest stakes; requires the guardrail maturity earned in phases 1–2 |
| **4 — Expand (12 mo+)** | Financing agent (G), full negotiation analytics, portfolio agents for repeat buyers/PE | New revenue lines on a proven agent platform |

**Monetization summary:** AI tier on buyer subscriptions (scout + diligence), per-deal diligence/closing fees, higher close-rate on the existing 6–8% success fee, curation scale without headcount, and a proprietary comp-data asset that compounds.

---

## 5. Why this is defensible for Acquire specifically

Generic AI features are copyable; these agents feed on assets only the marketplace owns — **verified metrics syncs, the NDA-gated data rooms, the closed-deal comp corpus, and both sides of the conversation**. Every deal closed makes the scout, valuation, and diligence agents smarter, which attracts more supply and demand: the agentic layer turns the existing data flywheel into the product itself.
