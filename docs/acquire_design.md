# Acquire.com — Design & Implementation Research

> Research date: **13 July 2026**
> Method: public marketing pages, pricing pages, HTTP response-header analysis, and reverse-engineering of the production JavaScript bundles served from `acquire.com` and `app.acquire.com`. Items that could not be verified directly are explicitly marked **(inferred)**.

---

## 1. What Acquire.com Is

Acquire.com (formerly **MicroAcquire**, founded by Andrew Gazdecki in 2020) is the largest online marketplace for buying and selling profitable internet businesses — SaaS, e-commerce, agencies, content sites, newsletters, mobile apps, Shopify apps, marketplaces, crypto and AI businesses.

**Key stats advertised:** 500k+ registered entrepreneurs/buyers · $500M+ in closed deal volume · 2,000+ startups sold · typical exit "in as little as 90 days" · roughly 45% of submitted startups pass listing curation.

### Business model (two-sided marketplace, subscription + take-rate)

| Side | Revenue stream |
|---|---|
| **Buyers** | Freemium subscription: **Basic (free)** — browse public listing details only; **Premium (from ~$390/yr)** — full financials, direct founder contact, deals up to $250k; **Platinum** — all deal sizes, exclusive listings |
| **Sellers** | Monthly listing fee ($25 / $50 / $100 by asking-price tier) **plus** a closing/success fee of **8% / 7% / 6%** of the transaction value (<$250k / $250k–$1M / >$1M) |
| **Services** | "Guided by Acquire" advisory program for SaaS with $100k+ revenue; Acquire Academy (M&A courses); financing referral partnerships |

---

## 2. Tech Stack

### 2.1 Verified by direct inspection

| Layer | Technology | Evidence |
|---|---|---|
| Marketing site (`acquire.com`) | Static/prerendered HTML + vanilla JS, **webpack** bundles, FAQ structured-data (SEO), Google Fonts (Open Sans) | Hashed `index/polyfills/*.js` bundles; `webpack` signatures in bundle |
| Web app (`app.acquire.com`) | **React SPA** built with **Vite** (`<div id="root">`, ES-module preloaded `index`/`vendor` bundles, version tag `v80.0.9` in asset names) | App HTML + vendor bundle (1,260 `react` refs) |
| State management | **MobX** | 261 signatures in vendor bundle |
| UI / styling | **Material UI (MUI)** + **Emotion** CSS-in-JS, react-dnd (drag & drop) | Vendor bundle signatures |
| Authentication | **Firebase Auth** (`authDomain: app.acquire.com`), email + **Google OAuth** + **LinkedIn** login; `securetoken.google.com` token exchange | Firebase config object in bundle |
| Primary database | **Cloud Firestore** (realtime listeners; `experimentalAutoDetectLongPolling` enabled) | 416 `firestore` signatures |
| Secondary database | **Firebase Realtime Database** (`https://microacquire.firebaseio.com`) | Config in bundle |
| File storage | **Google Cloud Storage / Firebase Storage** (`microacquire.appspot.com`) | Config in bundle |
| Backend compute | **Firebase Cloud Functions** invoked via `httpsCallable` (serverless API + business logic) | Functions SDK client code in bundle |
| Abuse protection | **Firebase App Check** | `content-firebaseappcheck.googleapis.com` in bundle |
| Payments | **Stripe** (Stripe.js — buyer subscriptions, seller fees) | 63 signatures, `js.stripe.com` |
| Identity verification (KYC) | **Persona** (`withpersona.com`) with 4 inquiry templates: buyer, seller, seller-business, beneficiary | Template IDs (`itmpl_…`) in config |
| Metrics sync | **ChartMogul API** + **Metricable API** (OAuth) — sellers connect real MRR/churn data to listings | Integration config objects with API URLs |
| Escrow | **Escrow.com** partner integration | Partner URL in bundle |
| Banking partner | **Mercury** (referral) | Partner URL in bundle |
| CDN / edge | **Fastly** in front of both `acquire.com` and `app.acquire.com` (consistent with Firebase Hosting, which is fronted by Fastly) | `X-Served-By: cache-*` response headers |
| Error monitoring | **Sentry** incl. Session Replay (`maskAllText`, `blockAllMedia` config present) | 246 signatures |
| Analytics | **Segment** (CDP), **Google Tag Manager + GA**, **Facebook Pixel**, Amplitude traces | Bundle + inline GTM/FB snippets |
| Feature flags | Custom config-driven flags: `AdvisorsForSellers`, `BuyerTrialViews`, `RecastFinancialList`, `SellerDiscountCoupon`, `MetricableLogin`, `ExpeditedReminders`, `CheckMaintenanceMode`, `HealthCheck`, `EnvLockMode`, `AllowDevLogin` | Flag object in bundle |
| Blog | **WordPress** on nginx (`blog.acquire.com`) | Response headers |
| Help center | Cloudflare-fronted knowledge base (`help.acquire.com`) | Response headers |

### 2.2 Inferred (not directly observable)

- **Language:** TypeScript on both frontend and Cloud Functions (industry norm for this stack) **(inferred)**
- **Search/filtering:** listing search appears to be served through Firestore queries / Cloud Functions rather than a dedicated engine — no Algolia/Typesense/Elastic signatures found in the bundles
- **Email/notifications:** transactional email provider (e.g. SendGrid/Postmark) driven from Cloud Functions; Slack alert integration is advertised for buyers **(inferred mechanism)**
- **Admin/curation tooling:** internal admin app for the listing-curation team (~45% acceptance rate implies a human review queue) **(inferred)**

### 2.3 Architecture style — summary

A **serverless, Backend-as-a-Service (BaaS) architecture on Google Cloud/Firebase**: a React SPA talks directly to Firebase Auth/Firestore/Storage with security rules + App Check, while privileged business logic (payments, escrow, KYC, metrics sync, notifications) runs in Cloud Functions that orchestrate third-party APIs. This is a pragmatic, small-team-friendly design: no servers to manage, realtime updates for free (chat, listing alerts), and pay-per-use scaling.

---

## 3. Architecture Diagram

- **Excalidraw file (editable, in `docs/diagrams/`):** [`acquire_architecture.excalidraw`](./diagrams/acquire_architecture.excalidraw) — open at [excalidraw.com](https://excalidraw.com) via *File → Open*
- **Shareable link:** https://excalidraw.com/#json=s-8abaVaFWyDr52-u-ic9,_h5kZwWtP7yFllkvFr3OZw

Text view of the same architecture:

```
 Buyer (browser)      Seller (browser)      Visitor (SEO)
        |                    |                   |
        +--------------------+-------------------+
                             v
                 Fastly CDN (edge cache, TLS)
                             |
   +-------------------------+---------------------------+
   |  FRONTEND                                            |
   |  Marketing site      Web app (app.acquire.com)  Blog/Help
   |  static JS/webpack   React+Vite · MobX · MUI    (WordPress /
   |  SEO pages, GTM/GA                               Cloudflare)
   +-------------------------+---------------------------+
                auth |       | API (httpsCallable)    \  client SDKs
                     v       v                          v (Stripe.js, Persona)
   +--------------------------------------+   +---------------------+
   | BACKEND — Firebase on Google Cloud   |   | 3RD-PARTY SERVICES  |
   |  Firebase Auth   App Check           |   |  Stripe (billing)   |
   |  Cloud Functions (business logic) ------>|  Persona (KYC)      |
   |     |            |           |       |   |  Escrow.com         |
   |     v            v           v       |   |  ChartMogul /       |
   |  Firestore   Realtime DB  Storage    |   |  Metricable         |
   |  (listings,  (presence)   (docs)     |   +---------------------+
   |   deals, chat — realtime)            |
   +--------------------------------------+
                     |
      Observability & Analytics: Sentry · Segment · GA4/GTM · FB Pixel
```

### Key data flows

1. **Listing creation:** Seller → app → Cloud Functions → Firestore; metrics pulled from ChartMogul/Metricable/Stripe; human curation approves (~45% pass) → listing goes live.
2. **Discovery:** Buyer filters/searches listings (Firestore queries); saved-search alerts pushed via email/Slack.
3. **Access control:** Buyer subscribes (Stripe) + verifies identity (Persona) + auto-signs NDA → unlocks private financials from Storage/Firestore.
4. **Deal:** In-app chat (Firestore realtime) → LOI builder → APA builder → Escrow.com closes funds transfer → success fee charged.

---

## 4. Full Feature List (as shipped by Acquire.com)

### Seller-side
1. Guided listing builder (business details, reason for sale, asking price)
2. Free automated valuation tool (SaaS multiples)
3. Financial metrics sync — ChartMogul, Metricable, Stripe (verified MRR/ARR/churn on the listing)
4. Financial recasting of P&L (`RecastFinancialList` flag)
5. Listing curation/vetting by Acquire's team before publication
6. Anonymous listings (identity revealed only after NDA)
7. Multi-channel listing promotion (email blasts to 500k+ buyers, featured placements)
8. Buyer-quality signals: verified ID, proof of funds, buyer intro/acquisition thesis
9. Automated NDA collection from interested buyers
10. In-app messaging with buyers
11. Offer management (receive/compare LOIs — avg ~10 offers per listing)
12. Legal document builders (LOI, APA)
13. Free escrow via Escrow.com
14. "Guided by Acquire" — M&A advisor program for $100k+ revenue SaaS
15. Advisor directory (`AdvisorsForSellers` flag)
16. Dedicated customer success manager; 24/7 support
17. Seller pricing tiers with monthly listing fee + closing fee

### Buyer-side
18. Marketplace browse/filter: industry, asking price, revenue, profit, multiples, tech stack, location
19. Public vs. private listing detail (freemium gate)
20. Buyer subscription tiers (Basic / Premium / Platinum) via Stripe
21. Identity verification (Persona) and proof-of-funds verification
22. Auto-signed NDAs for instant data-room access
23. Saved searches + instant new-listing alerts (email, Slack)
24. Standardized financial snapshots, P&L summaries, customer/traffic metrics
25. Direct founder chat (realtime)
26. LOI/offer builder ("make an offer in minutes")
27. APA builder and AI-assisted legal/diligence/closing tools
28. Acquisition financing options (SBA and lender referrals)
29. Acquire Academy — M&A course content
30. Expert/advisor guidance on deals
31. Watchlist/favorites and deal pipeline tracking

### Platform / trust / operations
32. Listing curation workflow (approve/reject with feedback)
33. Fraud prevention: KYC, App Check, NDA gating, anonymized listings
34. Notifications engine (email, in-app, Slack; reminder cadences — `ExpeditedReminders`)
35. Feature flags, maintenance mode, health checks
36. Analytics pipeline (Segment → GA/Amplitude/FB) and error monitoring w/ session replay (Sentry)
37. Content marketing: blog, help center, valuation guides, SEO category pages (e.g. `/saas-companies-for-sale/`)
38. Referral program ("refer a business")

---

## 5. MVP Feature Set (recommended subset)

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

## 6. Functional Requirements

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

## 7. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | Listing search p95 < 500 ms; page TTI < 3 s on 4G; realtime message delivery < 1 s |
| **Scalability** | Support 100k+ listings and 500k+ users without re-architecture; serverless auto-scaling (Functions/Firestore) preferred; fan-out alert jobs must handle publication spikes |
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

---

## 8. Sources

- [Acquire.com homepage](https://acquire.com/), [buyers page](https://acquire.com/buyers/), [sellers page](https://acquire.com/sellers/), [buyer pricing](https://acquire.com/pricing/), [seller pricing](https://acquire.com/seller-pricing/)
- Production bundle inspection: `app.acquire.com/assets/index-v80_0_9-*.js`, `vendor-v80_0_9-*.js` (Firebase config, Persona templates, ChartMogul/Metricable config, feature flags, library signatures)
- HTTP header analysis of `acquire.com`, `app.acquire.com`, `blog.acquire.com`, `help.acquire.com`
- [CT Acquisitions platform guide (2026)](https://ctacquisitions.com/microacquire-acquire-com-platform-guide/)
- [Escrow.com × MicroAcquire partnership page](https://www.escrow.com/partners/landing/microacquire)
