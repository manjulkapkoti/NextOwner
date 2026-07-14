# Baton.com — Architecture & Design Research

> Research date: **13 July 2026** · Second site in the competitive-research series (first: [`../acquire_design.md`](../acquire_design.md)).
> Method: marketing pages, HTTP header analysis, Next.js `__NEXT_DATA__` + build-manifest inspection, JS chunk signature scanning, sitemap enumeration, and **their own engineering blog** (a luxury Acquire didn't offer). Unverifiable items marked **(inferred)**.
> Verdict for NextOwner: see §6.

---

## 1. What Baton Is

Baton (baton.com, NYC) is a marketplace + tech-enabled brokerage for **main-street small businesses** — bakeries, HVAC companies, restaurants, service businesses — not just internet businesses like Acquire. Founded by ex-Zillow exec Chat Joglekar; ~$15M raised, including a [$10M Series A (Jan 2025) led by Obvious Ventures](https://fortune.com/2025/01/21/baton-zillow-private-equity-succession-real-estate-bakery-limprimerie/). Claims: $1.5B+ in platform listings across 2,000+ businesses, [750% YoY revenue growth](https://www.prnewswire.com/news-releases/baton-cements-leadership-in-smb-acquisition-market-with-750-revenue-growth-and-1-5b-in-platform-value-302521454.html), **70% close rate at ~half of traditional broker fees**.

### Business model — the key contrast with Acquire

| | Acquire.com | Baton |
|---|---|---|
| Inventory | Online businesses (SaaS, ecom, content) | Main-street SMBs (often offline) |
| Model | **Self-serve marketplace** (software does the work) | **Tech-enabled brokerage** (software + human advisors in every deal) |
| Revenue | Buyer subscriptions + 6–8% seller success fee | ~50% of a traditional broker's fee (success-fee weighted) |
| Trust mechanism | Metrics API sync + KYC + curation | **Financial reconciliation before listing** + advisor vetting |
| NDA model | Per-listing NDA + seller approval | **One platform-wide NDA** unlocks gated detail |
| Deal support | Templates + optional advisory tier | Weekly meetings, checklists, project-managed closing |

Baton is what Acquire's "Guided by Acquire" tier would look like as the *whole company*. The 70%-close-rate claim is the payoff of putting humans plus process into every deal.

---

## 2. Tech Stack

### 2.1 Verified by direct inspection

| Layer | Technology | Evidence |
|---|---|---|
| Marketing site (internal name **"Moondancer"**) | **Next.js** (pages router, SSG — `_ssgManifest`), TypeScript | `__NEXT_DATA__`, chunk names; their engineering blog |
| Content | **Contentful headless CMS** — every homepage section is a CMS entry | Contentful space `p2zgtwwed5ac` in `__NEXT_DATA__`; `ctfassets.net` images |
| Product app (internal name **"Storefront"**, served at `www.baton.com/market/*`) | **Remix** (Vite build — `entry.client-*.js`), migrated from Next.js | Module-preload asset graph on `/market/login` |
| UI | Chakra UI (historically; Emotion runtime visible), shared Figma design system, Storybook | Engineering blog + `emotion-element` chunk |
| Data fetching | **TanStack React Query** (query/mutation/infinite-query chunks); **GraphQL + Apollo** present in marketing bundle | Chunk names, `graphql` dedupe warnings |
| Auth | **SuperTokens** (open-source auth platform; session hooks) | `supertokens-*.js`, `useSession-*.js` chunks |
| Hosting | **AWS** — `Server: awselb/2.0` (ALB) on apex; self-hosted Next.js (`x-nextjs-cache`, no Vercel/CDN vendor headers) | Response headers |
| Domain layout | **One domain, path-based zones**: `/` marketing, `/baton-beat` blog, `/market/*` product app | Canonicals + differing asset pipelines per path |
| Feature flags | **LaunchDarkly** | SDK signatures + `clientstream.launchdarkly.com` |
| Analytics | **Segment**, GTM/GA, Amplitude traces | Bundle signatures |
| Error monitoring | **Sentry** (both apps) | 239 + 30 signatures |
| Consent/privacy | **Termly** (auto-blocking consent manager) | Script tag on every page |
| Fonts | Adobe Typekit + Google Fonts | `use.typekit.net` |
| Testing/process | TypeScript everywhere, Jest + RTL, Cypress, Storybook, tests-written-before-refactor | Engineering blog post |

### 2.2 Inferred

- **Backend:** not directly observable. GraphQL client-side + press mentions of a "valuation service, notifications service, behavioral data stack" suggest a **services-oriented backend on AWS behind a GraphQL API** (inferred). Early MVP work was done with [thoughtbot](https://thoughtbot.com/case-studies/baton-market) (a Rails consultancy), so Rails heritage is plausible (inferred).
- **Elena AI analyst** (see §4) implies a RAG pipeline over data-room documents — vector index + LLM with citation grounding (inferred implementation, verified feature).

### 2.3 Architecture sketch

```
                    www.baton.com  (AWS ALB, one domain)
        ┌───────────────────┬───────────────────────────────┐
        ▼                   ▼                               ▼
  /  Marketing        /baton-beat  Blog              /market/*  Product app
  "Moondancer"        (same Next.js + Contentful)    "Storefront"
  Next.js SSG + TS                                   Remix (Vite) + TS
  content ← Contentful CMS                           TanStack Query · Chakra/Emotion
        │                                            SuperTokens auth
        │                                            LaunchDarkly flags
        └──────────── Segment · Sentry · GTM · Termly ────────────┘
                                    │
                                    ▼
                     GraphQL API + services on AWS (inferred):
                     valuations · notifications · listings · data rooms
                                    │
                                    ▼
                     Data rooms (P&L, tax returns, owner videos)
                     + "Elena" AI analyst — RAG w/ page-level citations
```

Notable architectural contrasts with Acquire: **no BaaS** (custom API on AWS vs Firebase), **one domain with path zones** (vs `app.` subdomain — no CORS, shared cookies), **open-source auth** (SuperTokens vs Firebase Auth), **CMS-driven marketing** (vs hand-built static pages).

---

## 3. Product Features Observed

**Seller-side:** free business valuation (+ public calculator as lead magnet) · financial reconciliation/validation *before* listing goes live · anonymous listings · **off-market profiles** (see §4) · dedicated M&A advisor, weekly meetings, closing checklists · owner interview/walkthrough videos.

**Buyer-side:** browse/filter marketplace ("Explore") · **one platform NDA** unlocks gated details · full data rooms (P&L, tax returns, schedules) · **Elena AI analyst** over the data room · saved searches/alerts · informal offers on off-market profiles · advisor-supported negotiation and closing.

**Platform:** listing vetting via reconciled financials · referral program · public changelog + engineering blog (recruiting + SEO + trust) · behavioral analytics stack.

---

## 4. Cool Features Log (Baton)

*(Also recorded in [`cool_features.md`](./cool_features.md) — the running cross-site log.)*

1. **Elena — AI data-room analyst.** Buyers ask plain-language diligence questions ("why did margins dip in 2024?"); Elena reads the actual P&L/tax documents and answers **with citations to document + page number**. This is the Due-Diligence Agent from `agentic_scope.md` (proposal C), shipped. The citation grounding is the detail worth copying — it converts an LLM answer from "trust me" to "verify me."
2. **Off-Market Profiles.** Anonymous teaser listings for owners *not ready to sell but open to the right price* — buyers browse validated high-level financials and initiate contact; owners choose whether to engage. Brilliant supply-side growth hack: it captures sellers *years* before a broker could.
3. **One platform-wide NDA.** Sign once, see gated detail everywhere (vs Acquire's per-listing NDA ceremony). Massive friction reduction on the buyer side.
4. **Owner walkthrough videos.** A founder on camera explaining operations and why they're selling — cheap feature, huge trust and qualification signal.
5. **Financial reconciliation before listing.** Baton validates/reconciles the books *before* publication — "verified" is the product, not a badge.
6. **Public changelog + engineering blog.** Marketing, recruiting, and buyer-trust value from content they'd write internally anyway.

---

## 5. Functional Notes Worth Stealing (process, not product)

- **Tests before refactor:** they wrote characterization tests before their JS→TS migration — same philosophy as `testing_guide.md`.
- **Design tokens in Figma as source of truth**, Storybook for visual QA — overkill for a solo MVP, right instinct at team scale.
- **Unified stack so engineers aren't siloed** — NextOwner's single-language backend (Python) follows the same logic.

---

## 6. Relevance Verdict for NextOwner

### Adopt now (cheap, affects current specs)
| Idea | Impact on NextOwner |
|---|---|
| **One platform NDA + per-listing access approval** | Simplify Milestone 5: buyer signs the NDA once (a `users.nda_signed_at` field); each listing still needs the seller's access approval. Keeps the trust gate, kills repeat friction. Worth an update to spec 005 when written. |
| **Owner walkthrough video** | Add an optional `video_url` / upload to the listing builder (M2) — trivial cost, big differentiation. |
| **Path-based deploy layout** | Note for post-MVP deploy: serve SPA + FastAPI under **one domain** (e.g. `/api/*` proxied) like Baton's `/market/*` — eliminates CORS entirely. Local dev keeps two ports. |

### Adopt later (post-MVP roadmap)
| Idea | Where it fits |
|---|---|
| **Elena-style data-room AI with citations** | Validates `agentic_scope.md` proposal C as the flagship agentic feature — a competitor shipped it; citation grounding is the spec to copy. |
| **Off-market profiles** | New listing status (`off_market`) + informal-offer flow; a supply-growth feature once the core loop works. |
| **CMS-driven marketing pages** | The principle (content changes without deploys) — locally, markdown files rendered by the marketing page; Contentful-class CMS only at real scale. |
| **SuperTokens** | If hand-rolled JWT auth ever becomes a liability, SuperTokens is the open-source, self-hostable upgrade path **with a Python/FastAPI SDK** — swaps in without violating the local-first constitution. |

### Explicitly do NOT copy
- **The brokerage-hybrid model** (humans in every deal) — it's Baton's business, not their software, and it doesn't fit a solo-built self-serve MVP. NextOwner stays Acquire-style self-serve; a "guided" tier is a monetization idea for much later.
- **GraphQL** — with one client and one API, REST + Pydantic (constitution Article 1/4) is simpler and matches spec-driven development; GraphQL earns its complexity only with many clients/consumers.
- **Two frontend frameworks under one domain** (Next.js + Remix) — an artifact of their migration history, not a goal.

---

## 7. Sources

- [baton.com](https://www.baton.com/) — homepage, sitemap, `/market/login`, JS bundles, headers
- [How we built Baton's frontend (engineering blog)](https://www.baton.com/baton-beat/refactoring-for-the-future-how-we-built-batons-frontend)
- [Product Spotlight June 2026 — Elena AI analyst](https://www.baton.com/baton-beat/product-spotlight-june-2026)
- [Introducing Private Listings / Off-Market Profiles](https://www.baton.com/baton-beat/introducing-private-listings-the-future-of-off-market-business-connections)
- [Fortune — Baton raises $10M Series A](https://fortune.com/2025/01/21/baton-zillow-private-equity-succession-real-estate-bakery-limprimerie/) · [AlleyWatch coverage](https://alleywatch.com/2025/01/baton-smb-marketplace-acquisitions-chat-joglekar/) · [PR Newswire — 750% growth](https://www.prnewswire.com/news-releases/baton-cements-leadership-in-smb-acquisition-market-with-750-revenue-growth-and-1-5b-in-platform-value-302521454.html)
- [thoughtbot case study — Baton MVP mobile app](https://thoughtbot.com/case-studies/baton-market)
