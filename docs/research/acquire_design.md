# Acquire.com — Design & Implementation Research

> **What this is:** a **teardown of a competitor** — reference material, like its siblings in this folder. **Nothing here is binding on NextOwner.** It describes what *Acquire* built; read it to learn from them, never to derive a requirement from them.
>
> **Where NextOwner's requirements went (restructured 2026-07-16).** This file used to double as the requirements source of truth — its MVP scope, FRs and NFRs are now **[`../requirements.md`](../requirements.md)**, which is what specs cite. That split happened because the two jobs had merged: an NFR here demanded scale *"without re-architecture"* while prescribing Acquire's serverless stack — the one constitution Article 1 rejects — and it read as binding for nine milestones. A teardown's findings are worth keeping **as findings**; the failure mode is losing the attribution.
>
> **§4** (the component-by-component architecture walkthrough) moved here from `design_implementation.md` Part 2 in the same pass, so Acquire's architecture and the diagram it explains live in one place.
>
> Research date: **13 July 2026**
> Method: public marketing pages, pricing pages, HTTP response-header analysis, and reverse-engineering of the production JavaScript bundles served from `acquire.com` and `app.acquire.com`. Items that could not be verified directly are explicitly marked **(inferred)**. *Note the limits of that method: it observes a stack, not a service-level objective — this file cannot tell you Acquire's real p95 or uptime.*

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

- **Excalidraw file (editable, in `docs/diagrams/`):** [`acquire_architecture.excalidraw`](../diagrams/acquire_architecture.excalidraw) — open at [excalidraw.com](https://excalidraw.com) via *File → Open*
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


## 4. Every Component in Acquire's Architecture, Explained

Open the diagram from §3 (`../diagrams/acquire_architecture.excalidraw`) side by side with this section — this is the component-by-component walkthrough of it. We go top to bottom. This part describes **what Acquire actually runs**; each backend item also names its equivalent in **NextOwner's FastAPI build** ([`../design_implementation.md`](../design_implementation.md) Part 3). *(Moved here 2026-07-16 from `design_implementation.md` Part 2, so that Acquire's architecture and its diagram live in one place — see that file's Part 2 pointer.)*

### Row 1 — Clients

**`Buyer (browser)` / `Seller (browser)` / `Visitor (SEO / content)`**
Not software you build — these are the three kinds of people hitting your site, and they matter because each needs a _different entry surface_:

- Buyers and sellers use the **logged-in web app** (rich, interactive).
- Visitors arrive from Google searches like "sell my SaaS" and hit the **marketing site** (fast, SEO-optimized). They are future users — the funnel starts here.

### Row 2 — `Fastly CDN — edge cache & TLS`

A **CDN (Content Delivery Network)** is a worldwide network of cache servers. Your app's files get copied to servers near users, so a visitor in India doesn't wait for a server in the US. It also terminates TLS (the `https://` lock).
**Locally: you don't build this.** Your Vite dev server plays this role on `localhost`. The CDN concept only matters at deploy time — knowing it exists is enough for now.

### Row 3 — Frontend layer

**`Marketing Site — acquire.com` (static HTML/JS, SEO pages)**
A plain, fast website: homepage, "how it works," pricing, category landing pages ("SaaS for sale"). It is _static_ (pre-built HTML files, no login) because Google ranks fast static pages well, and because it must load instantly for strangers.
**Locally:** one `index.html` landing page is plenty at first, or skip it entirely — the MVP's value is in the app. If you build it, plain HTML + CSS in a `/marketing` folder served by any static server.

**`Web App — app.acquire.com` (React SPA · Vite · MobX · MUI + Emotion)**
The real product — everything behind login. Unpacking each term:

- **React** — the UI library; you compose the screen from components (`<ListingCard>`, `<ChatWindow>`).
- **SPA (Single-Page Application)** — the browser downloads the app once; after that, navigation swaps components without full page reloads. Feels like a desktop app.
- **Vite** — the build tool / dev server. Runs your app locally with instant hot reload (`npm run dev`).
- **MobX** — state management: one shared, observable place to keep "who is logged in," "current listing," "unread messages," so any component can react when data changes. (Alternative for beginners: Zustand or plain React context — simpler; MobX is what Acquire uses.)
- **MUI (Material UI)** — a library of pre-styled components (buttons, tables, dialogs) so you don't hand-craft CSS for everything. **Emotion** is the CSS-in-JS engine MUI uses under the hood — you get it automatically with MUI.

**In your build: the frontend is unchanged** — this layer survives the backend swap untouched; only the small data-access module changes (a `fetch` wrapper instead of the Firebase SDK).

**`Blog — WordPress` / `Help Center`**
Content marketing (SEO articles) and support docs. Completely separate systems in real life. **Locally: skip.** A `docs/faq.md` file can stand in.

### Row 4 — Backend: "Firebase on Google Cloud (serverless)" — what Acquire runs

**What "serverless / BaaS" means and why Acquire chose it:** instead of writing and operating your own server + database + auth system, Firebase gives you ready-made building blocks that the frontend talks to directly, secured by rules. A tiny team gets auth, a realtime database, file storage, and an API runtime without managing a single machine. The trade-off: you write logic in _their_ shapes (security rules, cloud functions) rather than a classic API server.

> **Crucial for you:** you are **not** rebuilding this Firebase stack. NextOwner's build ([`../design_implementation.md`](../design_implementation.md) Part 3) replaces this entire zone with a **Python FastAPI service + SQL database** — a classic API-owns-everything architecture. Read this section to understand what each piece does for Acquire; each entry names your FastAPI equivalent.

**`Firebase Auth` (email · Google · LinkedIn)**
Handles sign-up, login, password reset, OAuth ("Continue with Google"), and issues a **JWT token** — a signed proof of identity the frontend attaches to every request. Acquire never stores passwords itself.
_In the deal flow:_ every action (listing, NDA, offer) hangs off the verified user identity this provides.
**In your build:** FastAPI auth endpoints — bcrypt-hashed passwords, JWT issued at login, verified on every request by a `get_current_user` dependency (§3.6). Same concept: prove identity once, carry a signed token.

**`App Check` (abuse protection)**
Verifies requests come from _your real app_, not a bot or a script replaying your API. Anti-scraping/anti-abuse armor.
**In your build: skip.** A production concern; its equivalent later would be rate-limiting middleware.

**`Cloud Functions` (API & business logic)**
Small server-side functions that run on demand — the only place where _privileged_ logic lives in Acquire's design. Two flavors:

1. **Callable functions** (`httpsCallable`) — the frontend calls them like an RPC: `submitOffer({listingId, price})`. Used whenever the client must not be trusted — approving a listing, recording an NDA acceptance, moving money.
2. **Trigger functions** — run automatically on events: "when a new listing document is created → find matching saved searches → send alert emails."
   _Why not do everything in the frontend?_ Anything a user's browser does, a malicious user can fake. Rule of thumb: **anything with rules-of-the-game (state machines, fees, notifications) must run server-side.**
   **In your build:** this entire role is played by FastAPI — callables become **POST endpoints**, triggers become code that runs inside the endpoint or as a **BackgroundTask** after it.

**`Cloud Firestore` (listings · deals · chat — realtime sync)**
Acquire's main database — a **NoSQL document database** (collections of JSON-like documents) whose killer feature is **realtime listeners**: the frontend _subscribes_ to a query and gets pushed updates the instant data changes — that's how chat messages and new listings appear without refreshing. Access is governed by **security rules** enforced by the database itself, because clients talk to it directly.
**In your build:** SQL tables (SQLite → Postgres later) that only the API can reach — the browser never touches the database. The realtime trick is replaced by **WebSockets** for chat (Milestone 6) and simple refetch/polling elsewhere.

**`Realtime Database` (presence & counters)**
Firebase's older, simpler realtime DB. Acquire still carries it (the app config points at `microacquire.firebaseio.com`) — typical for "is user online?" presence dots, plus legacy data from the MicroAcquire days.
**In your build: skip entirely** — historical baggage, not a design goal.

**`Cloud Storage` (docs · uploads · P&L)**
File storage (like a private Dropbox) for P&L PDFs, metric screenshots, logos. Files are referenced from database records and guarded by storage rules — this is the "data room."
**In your build:** an `uploads/` folder on disk, with files served **only through permission-checked FastAPI endpoints** — which actually makes the data-room gate more explicit than rules: one function decides who may download.

### Row 4, right — Third-party services

These are the "buy, don't build" decisions. Each one replaces months of specialist work. **Locally you mock all of them** — the mock teaches you the _interface_ while costing nothing:

| Service                                    | What it does for Acquire                                                                                  | Local substitute                                                                                                                                                                                |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Stripe** (plans & billing)               | Charges buyer subscriptions and seller fees; handles cards, invoices, taxes                               | Post-MVP. When you get there: Stripe **test mode** + Stripe CLI forwarding webhooks to your FastAPI endpoint — free, no real money. For the MVP, a `subscription_tier` column you flip by hand. |
| **Persona** (KYC verification)             | Government-ID + selfie identity checks for buyers/sellers                                                 | A stub "verification" page with an _Approve/Reject_ button that an admin clicks. Same data shape (`status: pending → verified`), zero vendor.                                                   |
| **Escrow.com** (secure closing)            | Neutral party holds buyer's money during asset transfer                                                   | A mocked `escrow_status` state machine on the deal record (`initiated → funded → released`) driven by buttons.                                                                                  |
| **ChartMogul / Metricable** (metrics sync) | Pulls _verified_ MRR/churn from the seller's billing system into the listing, so buyers trust the numbers | Seed JSON fixtures ("fake ChartMogul responses") served by a mock FastAPI route.                                                                                                                |

The **two arrows** into this zone in the diagram matter conceptually:

- `client SDKs` (dashed, from the web app) — some vendors run _in the browser_ (Stripe's card form, Persona's ID-capture widget) so sensitive data never touches your servers.
- `APIs` (from the backend) — the server-to-server calls and **webhooks** (vendor calls _you back_: "payment succeeded") where the real state changes happen. Never trust the client's word that a payment happened — trust the webhook.

### Bottom bar — Observability & Analytics

**Sentry** (crash reports + session replay of what the user did before the bug), **Segment** (routes product events like `listing_published` to analytics tools), **GA4/GTM/FB Pixel** (marketing measurement), **feature flags** (turn features on/off from config without redeploying — you saw Acquire's real flags like `AdvisorsForSellers`).
**Locally:** `console.log` / Python `logging` is your Sentry, and a `flags.py` / `flags.ts` with booleans is your feature-flag system. Worth _imitating cheaply_ — wrap analytics in your own `track(event, props)` function that just logs; later you point it at a real vendor without touching call sites.

---

## 5. Full Feature List (as shipped by Acquire.com)

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

## 6. Sources

- [Acquire.com homepage](https://acquire.com/), [buyers page](https://acquire.com/buyers/), [sellers page](https://acquire.com/sellers/), [buyer pricing](https://acquire.com/pricing/), [seller pricing](https://acquire.com/seller-pricing/)
- Production bundle inspection: `app.acquire.com/assets/index-v80_0_9-*.js`, `vendor-v80_0_9-*.js` (Firebase config, Persona templates, ChartMogul/Metricable config, feature flags, library signatures)
- HTTP header analysis of `acquire.com`, `app.acquire.com`, `blog.acquire.com`, `help.acquire.com`
- [CT Acquisitions platform guide (2026)](https://ctacquisitions.com/microacquire-acquire-com-platform-guide/)
- [Escrow.com × MicroAcquire partnership page](https://www.escrow.com/partners/landing/microacquire)
