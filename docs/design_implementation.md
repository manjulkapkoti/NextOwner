# Design & Implementation Guide (Local-First)

- **Product name:** **NextOwner** — decision recorded in [`specs/000-constitution.md`](../specs/000-constitution.md), Article 4.
- **Audience:** someone new to both the M&A-marketplace business and this architecture, who wants to build the MVP **entirely on a local machine** — no cloud account, no credit card.
- **Chosen stack:**
  - Frontend: **React** (mirroring Acquire's real stack)
  - Backend: **Python FastAPI**
  - Database: **SQL** (SQLite now → Postgres later)
  - Note: a deliberate deviation from Acquire's Firebase backend — see Part 3 for why.
- **Companion documents:**
  - [`requirements.md`](./requirements.md) — **NextOwner's requirements** (MVP scope F1–F12, FR-1…23, NFRs) — what specs cite
  - [`research/acquire_design.md`](./research/acquire_design.md) — the Acquire.com teardown (reference only, binding on nobody)
  - [`agentic_scope.md`](./agentic_scope.md) — the post-MVP AI/agentic roadmap
- **Design diagrams** (regenerate any of them via [`diagrams/diagGenerator`](./diagrams/diagGenerator/README.md)):
  - **Business workflow** — product-owner view of Part 1's deal lifecycle, as swim-lanes:
    - Editable file: [`nextowner_business_workflow.excalidraw`](./diagrams/nextowner_business_workflow.excalidraw) — open at [excalidraw.com](https://excalidraw.com) via _File → Open_
    - View-only HTML: [`nextowner_business_workflow.html`](./diagrams/nextowner_business_workflow.html) — open in any browser
    - Published link (snapshot at publish time): [view on excalidraw.com](https://excalidraw.com/#json=EdY0b8lOap89N9jte_1_u,o7BV81d9xVf8CQCvG8mhSw)
  - **System architecture** — technical view of Part 3's stack:
    - Editable file: [`nextowner_system_architecture.excalidraw`](./diagrams/nextowner_system_architecture.excalidraw) — open at [excalidraw.com](https://excalidraw.com) via _File → Open_
    - View-only HTML: [`nextowner_system_architecture.html`](./diagrams/nextowner_system_architecture.html) — open in any browser
    - Published link (snapshot at publish time): [view on excalidraw.com](https://excalidraw.com/#json=AfTWqCn2eR0y152OZwndn,Ot0Y46e92jJZUfP75yEzsg)

---

## Part 1 — The Business, Explained From Zero

### 1.1 What problem does Acquire.com solve?

Thousands of people build small profitable internet businesses (a SaaS tool making $5k/month, a newsletter with 40k subscribers). At some point the founder wants to **sell** ("exit"). On the other side, there are people with money — indie investors, holding companies, first-time buyers — who would rather **buy** a working business than start from scratch.

Without a marketplace, these two groups find each other through brokers (expensive, slow, only for big deals) or cold outreach (risky, no trust). Acquire.com is the **middleman platform** that:

1. Collects businesses for sale into one searchable catalog,
2. Verifies that sellers are real and their numbers aren't fake,
3. Verifies that buyers are real and have money,
4. Gives both sides the tools to go from "hello" to "money wired, keys handed over" safely.

Think of it as **a real-estate portal + a dating app + a legal-workflow tool**, for internet businesses.

### 1.2 The actors

| Actor               | Who they are                  | What they want                                       |
| ------------------- | ----------------------------- | ---------------------------------------------------- |
| **Seller**          | Founder of an online business | Maximum price, fast close, no time-wasters           |
| **Buyer**           | Investor / entrepreneur       | Good business at fair price, honest data, no fraud   |
| **Platform (you)**  | The marketplace operator      | Many successful deals — that's what you get paid for |
| **Curator / admin** | Platform employee             | Only publish quality, truthful listings              |

### 1.3 How the platform makes money

1. **Buyer subscriptions** — browsing basic info is free; seeing full financials and contacting sellers costs a yearly fee (~$390+). This filters out tourists and pays for the site.
2. **Seller fees** — a small monthly listing fee ($25–$100) plus a **success fee** of 6–8% of the sale price, charged only when the deal closes. This is the big revenue line: sell a $500k business, the platform earns ~$35k.
3. **Services** — advisory programs, courses, financing referrals.

Key insight: revenue depends on **closed deals**, so everything in the product design pushes deals toward closing: verified data (less fear), templates (less lawyer time), escrow (less fraud), chat and alerts (less waiting).

### 1.4 The deal lifecycle (the core business workflow)

This is the single most important thing to understand — every feature exists to serve one of these steps:

```
SELLER SIDE                      PLATFORM                       BUYER SIDE
-----------                     ----------                      ----------
1. Create listing  ─────────►  2. Curation review
   (metrics, story,               (approve ~45%,
    asking price)                  reject the rest)
                                       │ approved
                                       ▼
                               3. Listing goes LIVE  ─────────► 4. Buyer discovers it
                                  (anonymous public card)          (search, filters, alerts)
                                                                       │ interested
                                       ┌───────────────────────────────┘
                                       ▼
                               5. Buyer signs NDA ◄── digital signature, timestamped
                                       │
6. Seller approves access  ◄───────────┘
        │
        ▼
7. Private data revealed ──────────────────────────────────► 8. Buyer studies financials
   (company name, P&L,                                          ("due diligence" lite)
    real metrics)                                                    │
        ▲                                                            ▼
        └──────────────── 9. CHAT: questions & answers ◄─────────────┘
                                       │
                                       ▼
                              10. Buyer makes an OFFER (LOI)
                                  price + terms + conditions
                                       │ seller accepts
                                       ▼
                              11. Deep due diligence + APA
                                  (final contract)
                                       │ both sign
                                       ▼
                              12. ESCROW: buyer's money held
                                  by neutral 3rd party
                                       │
                              13. Asset transfer: domain, code,
                                  accounts, customers move to buyer
                                       │ buyer confirms
                                       ▼
                              14. Escrow releases money to seller
                                  Platform charges success fee. DONE.
```

### 1.5 Glossary (terms you'll keep seeing)

| Term              | Meaning                                                                                                              |
| ----------------- | -------------------------------------------------------------------------------------------------------------------- |
| **NDA**           | Non-Disclosure Agreement — buyer promises to keep the seller's private data secret. Gate before seeing real numbers. |
| **LOI**           | Letter of Intent — a _non-binding_ offer: "I intend to buy for $X under conditions Y." Starts serious negotiation.   |
| **APA**           | Asset Purchase Agreement — the _binding_ final contract listing exactly what's sold (domain, code, customers…).      |
| **Escrow**        | A neutral third party holds the buyer's money until the seller delivers the assets. Protects both sides.             |
| **Due diligence** | The buyer's investigation: are the revenue numbers real? Any legal problems? Why is churn rising?                    |
| **MRR / ARR**     | Monthly / Annual Recurring Revenue — the standard "size" measure of a SaaS business.                                 |
| **Churn**         | % of customers who cancel per month. High churn = leaky bucket = lower price.                                        |
| **TTM**           | Trailing Twelve Months — revenue/profit over the last 12 months.                                                     |
| **Multiple**      | Price ÷ profit (or revenue). "Sold at 3.5× profit" is how these businesses are priced.                               |
| **KYC**           | Know Your Customer — identity verification (passport/ID selfie) to prevent fraud.                                    |
| **P&L**           | Profit & Loss statement — the standard financial summary document.                                                   |
| **Curation**      | Human review of listings before publishing — the platform's quality filter.                                          |
| **Data room**     | The folder of private documents (P&L, contracts, metrics) a buyer gets access to after the NDA.                      |

---

## Part 2 — Acquire's Architecture *(moved — see `research/acquire_design.md`)*

> **Moved 2026-07-16.** Acquire's architecture — the diagram **and** the component-by-component walkthrough that used to live here — is now in one place with the rest of the Acquire teardown: **[`research/acquire_design.md`](./research/acquire_design.md) §3 (diagram) + §4 (walkthrough)**. Nothing was lost.
>
> **Why:** it was reference material about *someone else's* product sitting in NextOwner's implementation guide, and the walkthrough was separated from the very diagram it explains. **This guide now contains only NextOwner's design.** The Part numbering is unchanged so existing references still resolve.
>
> **NextOwner's architecture is Part 3** (stack, data model, the NDA gate, horizontal scale) **and Part 5** (the mental model).

---

## Part 3 — Local Development Setup (React + FastAPI + SQL)

> **Why FastAPI here, when Acquire uses Firebase?** Three good reasons: (1) **Python is the language of the AI/agentic layer** you plan to add later (`agentic_scope.md`) — agents, LLM SDKs, and your API will live in one language and one service; (2) FastAPI is the industry-standard Python web framework, with automatic request validation (Pydantic) and auto-generated API docs — a great match for spec-driven development; (3) you learn the most transferable skills: REST design, SQL, JWT auth. **The trade-off:** you give up Firebase's free realtime sync and declarative security rules — §3.6 and Milestone 6 show how FastAPI covers both.
> A no-custom-backend alternative (Supabase) is kept for comparison in [`research/supabase_alternative.md`](./research/supabase_alternative.md).

### 3.1 The local stack at a glance

```
┌────────────────────────────── YOUR MACHINE ──────────────────────────────┐
│                                                                          │
│  Browser ──► Vite dev server (localhost:5173)   ← the React app          │
│                   │                                                      │
│                   │  Vite proxies /api/* & /ws/* to FastAPI — 1 origin   │
│                   ▼                                                      │
│  FastAPI (localhost:8000, hot reload via `fastapi dev`)                  │
│    • /docs        — auto-generated Swagger UI ← your API playground      │
│    • auth.py      — register/login, bcrypt hashing, JWT issue/verify     │
│    • permissions.py      — permission dependencies ← THE NDA GATE LIVES HERE    │
│    • routers/     — listings, admin, access, chat, offers, searches      │
│    • BackgroundTasks — alert fan-out when a listing goes live            │
│    • SQLModel ORM                                                        │
│                   │                                                      │
│                   ▼                                                      │
│  SQLite file (nextowner.db) → swap to Postgres in Docker later:          │
│                               same code, new connection string           │
│  uploads/ folder            → data-room files, downloadable ONLY         │
│                               through permission-checked endpoints       │
│                                                                          │
│  Mocks: Persona-stub page, escrow state machine, metrics fixtures        │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Prerequisites (install once)

1. **Node.js 20+** — you already have v20.13.1 ✔
2. **Python 3.12+** — you already have 3.12.3 ✔

That's the whole list: SQLite ships inside Python, so there is **no Docker, no Java, no cloud account, no emulator**. (Docker becomes optional later, only if/when you switch SQLite → Postgres.)

### 3.3 Project scaffold

```
NextOwner/
├── README.md                     # project entry point
├── docs/                         # research · guides · diagrams (this file lives here)
├── specs/                        # SDD constitution + per-milestone specs
├── app/                          # React SPA (created at Milestone 0)
│   ├── src/
│   │   ├── components/           # ListingCard, ChatWindow, OfferForm…
│   │   ├── pages/                # Marketplace, ListingDetail, Dashboard, Admin
│   │   ├── stores/               # MobX stores: authStore, listingStore, chatStore
│   │   └── lib/api.ts            # fetch wrapper that adds the JWT header
│   └── vite.config.ts
├── backend/                      # FastAPI (created at Milestone 0)
│   ├── app/
│   │   ├── main.py               # FastAPI app: CORS, routers mounted
│   │   ├── db.py                 # engine + get_session dependency
│   │   ├── models.py             # SQLModel tables — the schema (§3.5)
│   │   ├── schemas.py            # Pydantic request/response models
│   │   ├── auth.py               # hashing, JWT create/verify, get_current_user
│   │   ├── permissions.py               # permission dependencies (NDA gate!)
│   │   ├── routers/              # auth.py · listings.py · admin.py · access.py
│   │   │                         # chat.py · offers.py · searches.py
│   │   └── services/             # business logic + mocks/ (escrow, KYC, metrics)
│   ├── tests/                    # pytest — see testing_guide.md
│   ├── uploads/                  # data-room files (add to .gitignore)
│   └── requirements.txt
├── seed/seed.py                  # inserts demo users + ~30 fake listings
└── marketing/                    # optional static landing page
```

### 3.4 Key setup commands

```bash
# ── Backend (terminal 1) ─────────────────────────────────────────────
cd backend
python -m venv .venv
.venv\Scripts\activate                     # Windows
pip install "fastapi[standard]" sqlmodel pyjwt bcrypt python-multipart
fastapi dev app/main.py                    # → http://localhost:8000
# open http://localhost:8000/docs — interactive Swagger UI, free with FastAPI.
# You can exercise every endpoint from the browser before any frontend exists.

# ── Frontend (terminal 2) ────────────────────────────────────────────
npm create vite@latest app -- --template react-ts
cd app && npm i mobx mobx-react-lite @mui/material @emotion/react @emotion/styled react-router-dom
npm run dev                                # → http://localhost:5173
```

Three small glue pieces — wired **single-origin** (adopted from the Baton research, 2026-07-13): the browser talks only to the Vite server, which forwards API traffic to FastAPI. No CORS anywhere, and dev matches the production layout exactly.

**Route prefix** — every backend route is mounted under `/api` (WebSockets under `/ws`) in `backend/app/main.py`:

```python
from fastapi import FastAPI
from .routers import auth, listings, admin, access, chat, offers, searches

app = FastAPI(title="NextOwner API")
for r in (auth.router, listings.router, admin.router,
          access.router, offers.router, searches.router):
    app.include_router(r, prefix="/api")
app.include_router(chat.router, prefix="/ws")      # WebSocket routes
# No CORS middleware needed — the Vite proxy makes everything same-origin.
```

**Vite dev proxy** — in `app/vite.config.ts`:

```ts
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
```

**API client** — `app/src/lib/api.ts` (this replaces the whole Firebase SDK; note the relative URL):

```ts
export async function api(path: string, opts: RequestInit = {}) {
  const token = localStorage.getItem("token");
  const res = await fetch(`/api${path}`, {
    // relative → same origin
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...opts.headers,
    },
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.status === 204 ? null : res.json();
}
```

**Production twin (post-MVP):** one domain, a reverse proxy (nginx/Caddy/cloud LB) routes `/api/*` and `/ws/*` to FastAPI and everything else to the SPA's static build — exactly what the Vite proxy simulates locally, and exactly how Baton serves `baton.com/market/*`. Convention: **doc prose writes endpoint paths without the `/api` prefix for readability; code (fetch calls, tests) always includes it.**

#### Horizontal scale — what a second instance breaks (deferred-but-designed)

*Recorded 2026-07-16 (constitution amendment log). Post-MVP work — but the seams are named now so M1/M2/M6 are built with them in mind, not retrofitted.*

The moment that "cloud LB" above fronts **two** FastAPI processes instead of one, any state living *inside* a process becomes a bug. Acquire never faces this: Firebase is serverless, so the platform makes per-instance state physically impossible — which is why their NFR could promise 500k users "without re-architecture." NextOwner runs long-running processes and must earn that deliberately.

**Already correct — don't lose it:** **JWT auth is stateless.** No server-side session, so no sticky sessions and no shared session store. That is the single biggest load-balancer prerequisite and the architecture has it for free. The `permissions.py` gate, the public/private split, and the status state machines are all per-request logic — they scale untouched.

**The three blockers, and the fix for each:**

| # | Per-instance state | Symptom at instance #2 | Fix (post-MVP) | Owned by |
|---|---|---|---|---|
| 1 | **Auth rate limiting** — an in-process counter | N instances ⇒ N× the intended limit; brute-force protection quietly weakens | A shared store (Redis-class), or the limiter's own backend setting | **M1** |
| 2 | **Uploads on local disk** (`uploads/{listing_id}/`) | Instance A writes the file, instance B serves the download → 404 | Object storage (S3-class) behind the *same* permission-checked endpoint | **M2** |
| 3 | **The in-memory WebSocket registry** (`{conversation_id: [sockets]}` — Part 4, Milestone 6) | Buyer on instance A, seller on instance B — messages **silently never arrive**. No error; just a broken product. Also contradicts the 99.9%-uptime-for-chat NFR | Persist → **publish** to a pub/sub backplane (Redis, or Postgres `LISTEN/NOTIFY`) → each instance fans out to its own local sockets | **M6** |

(SQLite is a fourth, but it's already handled: Article 1 plans the Postgres swap as a connection-string change.)

**The rule that keeps this cheap:** none of the three is worth *building* now — local disk and an in-process dict are the right MVP implementations, and premature Redis is pure cost. What matters is that each sits **behind a small interface from day one**, exactly as Article 1 already does for the agentic layer (`VectorStore`, the model client): a `save(listing_id, file) → key` / `open(key)` storage port, and a `publish(conversation_id, message)` broadcast port. Then the swap is one adapter, and it never touches the routers, the NDA gate, or the tests. Write the dict; just don't let the routers know it's a dict.

**Why now, not later:** these are cheapest *before* the code exists. M1 and M2 are the next two milestones — after they ship, the same change means editing tested code instead of writing it right the first time. See `milestones.md` § Scope fold-ins (M1, M2, M6).

### 3.5 The data model (SQL tables)

The schema is relational — the full SQL version is written out in [`research/supabase_alternative.md`](./research/supabase_alternative.md) §3 (it's identical; both are standard SQL). In your build you declare it as **SQLModel** classes (SQLModel = SQLAlchemy + Pydantic, from the FastAPI author), and the tables are: `user`, `listing`, `listing_private`, `access_request`, `conversation`, `message`, `offer`, `offer_event`, `saved_search`, `watchlist`. The three most important ones:

```python
# backend/app/models.py
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone

def _utcnow() -> datetime:   # tz-aware UTC — datetime.utcnow is deprecated (3.12); same helper as backend/app/models.py
    return datetime.now(timezone.utc)

class Listing(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    status: str = "draft"     # draft|pending_review|live|under_offer|sold|rejected|paused
    # PUBLIC, anonymous part — safe to show anyone:
    type: str                 # saas|ecommerce|newsletter|…
    headline: str
    description: str
    asking_price: float
    ttm_revenue: float; ttm_profit: float
    mrr: float; churn_pct: float; customers: int
    created_at: datetime = Field(default_factory=_utcnow)
    published_at: datetime | None = None

class ListingPrivate(SQLModel, table=True):        # the data room (NDA-gated)
    listing_id: int = Field(foreign_key="listing.id", primary_key=True)
    company_name: str
    website_url: str
    detailed_financials: str                        # JSON string
    document_paths: str                             # JSON list of uploads/ paths

class AccessRequest(SQLModel, table=True):          # the access gate's ledger
    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    buyer_id: int = Field(foreign_key="user.id", index=True)
    status: str = "requested"                       # requested|approved|denied
    requested_at: datetime = Field(default_factory=_utcnow)
    decided_at: datetime | None = None
    # The NDA itself is platform-wide and user-level (Baton-style, adopted
    # 2026-07-13): users.nda_signed_at is stamped once; creating any access
    # request requires it to be set.
```

Two design rules to notice (they survived the stack change untouched):

1. **Public vs private split.** The anonymous card (`Listing`) and the confidential data (`ListingPrivate`) are _different tables served by different endpoints_ — so the NDA gate is enforced by the API, not by frontend politeness. Bonus in FastAPI: the public endpoint's Pydantic `response_model` physically cannot leak private fields — the schema strips anything not declared.
2. **Status state machines.** `listing.status` and `offer.status` are the business workflow encoded as data. Status transitions happen **only inside endpoints** that validate the move (`pending_review → live` requires an admin; `submitted → accepted` requires the seller).

### 3.6 The NDA gate as a permission dependency — the heart of the design

Here is the key conceptual shift from Firebase: there, clients talk to the database directly, so the _database_ must enforce access (security rules). In your architecture, **the API is the only door** — the browser can never reach SQLite/Postgres — so every privilege check lives in one place: **FastAPI dependencies**, small reusable functions that run before your endpoint does.

**The mechanism:** a dependency is a function you attach to an endpoint with `Depends(...)`. FastAPI runs it *before* the endpoint itself; whatever it returns is handed to the endpoint as an argument, and if it raises (e.g. `HTTPException(403)`) the endpoint never runs at all. That makes dependencies the natural home for checks that many endpoints share — and `permissions.py` is the file that collects them, **one function per trust boundary**:

| Gate in `permissions.py` | Question it answers | Used by |
| --- | --- | --- |
| `get_current_user` | "Who is making this request?" — decodes the JWT, loads the user; 401 if missing/invalid | every protected endpoint |
| `require_admin` | "Is this user an admin?" — 403 if not | curation (M3), verification (M10) |
| `require_private_access` | "May this buyer see this listing's data room?" — owner, or approved access request; 403 otherwise. **The NDA gate.** | private data + document downloads (M5) |
| `require_conversation_member` | "Is this user a participant in this chat?" | chat endpoints + WebSocket (M6) |

```python
# backend/app/permissions.py
from fastapi import Depends, HTTPException
from sqlmodel import Session, select
from .auth import get_current_user          # decodes the JWT → returns User
from .db import get_session
from .models import Listing, ListingPrivate, AccessRequest

def require_private_access(
    listing_id: int,
    user = Depends(get_current_user),
    s: Session = Depends(get_session),
) -> Listing:
    listing = s.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    if listing.owner_id == user.id:                       # the seller always may
        return listing
    approved = s.exec(select(AccessRequest).where(
        AccessRequest.listing_id == listing_id,
        AccessRequest.buyer_id == user.id,
        AccessRequest.status == "approved",
    )).first()
    if not approved:
        raise HTTPException(403, "NDA access not granted")   # ← THE GATE
    return listing
```

```python
# backend/app/routers/listings.py
@router.get("/listings/{listing_id}/private")
def private_data(listing: Listing = Depends(require_private_access),
                 s: Session = Depends(get_session)):
    return s.get(ListingPrivate, listing.id)

@router.get("/listings/{listing_id}/documents/{filename}")
def download_document(filename: str,
                      listing: Listing = Depends(require_private_access)):
    return FileResponse(f"uploads/{listing.id}/{filename}")   # same gate guards files
```

Notice how the endpoint reads like a sentence: if execution reaches the body, the caller has _already_ been verified — the endpoint only does its actual job. The same pattern gives you `require_admin` (curation) and `require_conversation_member` (chat). **One function per trust boundary, reused by every endpoint behind that boundary, tested directly in pytest** (`testing_guide.md` §4.1).

Why this file earns the "heart of the design" label:

1. **One place to look, one place to test.** A rule like "buyer without approved access is denied" exists in exactly one function, no matter how many endpoints sit behind that boundary (private data, document downloads, later the data-room AI). The M5 crown-jewel permission tests target these functions directly.
2. **It replaces what Firebase/Supabase do with rules/RLS** — same trust model, different address (compare [`research/supabase_alternative.md`](./research/supabase_alternative.md) §4).
3. **It's the future agent leash.** Per the constitution's agent-readiness note (Article 1): AI agents will act _as_ scoped users through these same gates, so an agent physically cannot read a data room its user wasn't approved for. The file you write in Milestone 1 is the same mechanism that keeps agents controllable later.

A useful mental shorthand for the whole backend: **routers say what the app does · `permissions.py` says who's allowed · services say how it works.** Keeping those three separated is most of what "clean backend architecture" means at this project's scale.

Your "inspection tooling" in this stack: **`/docs`** (Swagger UI — poke every endpoint by hand, the counterpart of the old Rules Playground) and any SQLite browser (e.g. _DB Browser for SQLite_, or the `sqlite3` CLI) as the counterpart of the Emulator UI's data viewer.

---

## Part 4 — Build Guide, Milestone by Milestone

Each milestone maps to the MVP features (F1–F12) in [`requirements.md`](./requirements.md) §1 (renumbered from M1–M12 on 2026-07-16 to avoid collision with milestone numbers); M12, appended by the gap review, extends past the F-list to close the deal loop. Build in this order — every step produces something clickable.

> **Testing:** every milestone below has a matching test checklist in [`testing_guide.md`](./testing_guide.md), plus the one-time framework setup. A milestone counts as _done_ when its tests pass and all earlier tests still pass.
> **Path convention:** endpoint paths below omit the `/api` prefix for readability (see §3.4) — in code it is always `/api/...`.

### Milestone 0 — Hello, FastAPI (half a day)

Scaffold per Part 3. Prove the loop end to end: a `GET /health` endpoint returning `{"status":"ok"}`, one throwaway `POST /sandbox` that writes a row and a `GET /sandbox` that reads it back, called from a React page. Click around `/docs`, look at `nextowner.db` in a SQLite browser. _You've now used the whole pipeline._

### Milestone 1 — Auth & roles (F1)

- `POST /auth/register` (email, password → bcrypt hash, role buyer/seller) and `POST /auth/login` (OAuth2 password form → JWT). `GET /auth/me` returns the current user from the token.
- `get_current_user` dependency decodes the JWT on every protected route; `require_admin` checks an `is_admin` column (set it by hand in the DB or via `seed.py` — your local stand-in for a real admin system).
- Frontend: MobX `authStore` keeps the token + user; router guards `/sell`, `/admin`.
- Google OAuth is a post-MVP nicety — email/password teaches the full mechanics first.

### Milestone 2 — Seller listing builder (F2 + uploads)

- Multi-step form (MUI Stepper): basics → metrics → story → documents → review.
- `POST /listings` creates a **draft** owned by the caller (server sets `owner_id` and `status` — never trust those from the client); `PUT /listings/{id}` edits while draft/paused; `POST /listings/{id}/submit` → `pending_review` (a server-controlled transition).
- `POST /listings/{id}/documents` accepts multipart uploads into `uploads/{listing_id}/`, storing paths in `ListingPrivate`.
- _Business lesson:_ structured metric fields (not free text) are what makes listings comparable and searchable — the marketplace's real product is standardized data.

### Milestone 3 — Admin curation queue (F3)

- `GET /admin/listings?status=pending_review` behind `require_admin`; `/admin` page renders the queue.
- `POST /admin/listings/{id}/approve` → `live` + `published_at`; `POST …/reject` stores the reason. Both validate the current status (you can't approve what isn't pending).
- _Business lesson:_ this human gate is Acquire's quality moat (~45% pass). Cheap to build, priceless to the brand.

### Milestone 4 — Marketplace browse + anonymous cards (F4, F5)

- `GET /listings?type=saas&min_profit=…&max_price=…` — filters become SQL `WHERE` clauses; pagination via `limit/offset`. Only `live` listings are ever returned.
- The response uses a `ListingPublic` Pydantic model — identity fields aren't in the schema, so the API _cannot_ leak them. The card's blurred/locked section advertises what the NDA unlocks (also the future paywall surface).
- `seed/seed.py` inserts ~30 fake listings so browsing feels real.

### Milestone 5 — Platform NDA + access gate (F6)

- **One platform-wide NDA (adopted from Baton, 2026-07-13):** the first time a buyer requests access anywhere, show the NDA modal → checkbox + button = click-wrap signature → `POST /auth/nda` stamps `user.nda_signed_at`. Signed once, never shown again.
- "Request access" on a listing → `POST /listings/{id}/access-request` (403 if the platform NDA isn't signed yet) creates the row with `status:"requested"`, timestamped (one per buyer-listing pair — enforce with a unique constraint). The per-listing audit trail survives; only the repeated signing ceremony is gone.
- Seller dashboard: `GET /access-requests?listing_id=…` with buyer profile → `POST /access-requests/{id}/approve|deny` (only the listing's seller may decide).
- The `require_private_access` dependency (§3.6) guards `GET /listings/{id}/private` **and** document downloads. **Verify in `/docs` that a non-approved buyer gets 403.** This milestone _is_ the product's trust core.

### Milestone 6 — Realtime chat (F7)

- Approving access also creates a `conversation` row.
- **WebSocket endpoint** `WS /ws/conversations/{id}?token=…`: verify the JWT and membership on connect, keep a tiny in-memory connection manager (`{conversation_id: [sockets]}`), persist each message to the DB, broadcast it to the other participant's socket. Two browser windows side by side update instantly. **The in-memory dict is single-instance-only by construction** — correct for the MVP, fatal behind a load balancer. Keep the fan-out behind a `publish(conversation_id, message)` port so a pub/sub backplane drops in later without touching this endpoint (Part 3 § *Horizontal scale*, blocker #3).
- This is the one place you hand-build what Firestore gave for free — it's ~40 lines and excellent learning. (Fallback if you want to defer WebSockets: poll `GET /conversations/{id}/messages?after=<timestamp>` every few seconds — ugly but fine at MVP.)
- Unread counters: a `last_read_at` per participant, updated when the window is open.

### Milestone 7 — Offers / LOI (F8)

- "Make an offer" form → `POST /offers` validates (access approved? listing live?) and writes the offer plus an `offer_event` audit row.
- `POST /offers/{id}/accept|decline|counter` — seller only, validates the current status, appends events.
- Accepting flips `offer.status="accepted"` **and** `listing.status="under_offer"` in one DB transaction — the state machine in action, atomically.
- MVP stops here; escrow/APA are mocked buttons on a "deal" page if you want the full lifecycle visible.

### Milestone 8 — Notifications engine + saved searches & alerts (F9)

- Buyers save current filters: `POST /saved-searches` (filters as a JSON column).
- In the approve endpoint (M3), add a **BackgroundTask**: after the listing goes live, match it against all saved searches and insert `notification` rows. `GET /notifications` powers an in-app inbox (poll it, or refetch on route change — fine for MVP).
- Email version: log to console, or run [MailHog](https://github.com/mailhog/MailHog) locally and send SMTP to it from Python (`smtplib`) — a real inbox UI at `localhost:8025` with zero external service.
- **Scope expanded (2026-07-16 gap review):** this milestone is also the general **notifications engine** (FR-22 + the FR-16 email fallback). Earlier milestones (M3/M5/M6/M7) emit notification event rows — listing approved/rejected, access requested/decided, new message, new offer — and M8 builds the delivery surface (the in-app inbox above + email) for **all** of them, alongside the saved-search fan-out. Without these events the two-sided loop stalls until someone happens to log in. Every delivery is caller-scoped.

### Milestone 9 — Watchlist (F10) — an hour

`POST /watchlist/{listing_id}` / `DELETE /watchlist/{listing_id}` toggle; `GET /watchlist` joins to listings for the "Watchlist" page.

### Milestone 10 — Manual buyer verification (F11)

- Buyer uploads a proof-of-funds doc → `buyer_verified:"pending"`.
- Admin reviews in `/admin` → sets `verified` → badge shows in access requests and chat.
- _This is your Persona mock_ — same states, no vendor. Swapping in real Persona later means replacing one page with their widget plus one webhook endpoint.

### Milestone 11 — Valuation calculator (F12)

- Public page, pure frontend: inputs (type, MRR/revenue, profit, growth, churn) → multiple lookup table → estimated range with a friendly explanation. (No backend needed — or make it your first fun `POST /valuation` endpoint if you prefer.)
- _Business lesson:_ this is a lead magnet — on the real site it captures seller emails before they list.

### Milestone 12 — Deal completion *(appended 2026-07-16 — gap review)*

The close is where the business model lives (the success fee recognizes at close — research synthesis law #6), and without `sold` rows the future comps corpus (`agentic_scope.md` proposal F) never accumulates. M7 deliberately stopped at `under_offer`; this milestone finishes the state machine:

- **`POST /listings/{id}/mark-sold`** (seller-only): `under_offer → sold`, stamps `sold_at`, records the **final sale price server-derived from the accepted offer** (never client-set — Article 2 #4), and moves the accepted offer to its terminal state — all in one transaction, with `listing_event` + `offer_event` audit rows.
- **`POST /listings/{id}/relist`** (seller-only — the deal fell through): `under_offer → live`; the accepted offer becomes terminal (the spec names the status); sibling offers follow the policy M7 decided.
- Terminal states weaken nothing: the NDA gate still guards a `sold` listing's private data; illegal transitions → 409.
- **Optional extensions** (from the Little Exits research, fine to defer): invoice artifact on completion (L2), the asset-transfer checklist state machine (L3), and mocked escrow states (`initiated → funded → released`) surfacing `error_handling.md` §5's escrow failure modes. (This supersedes the M7 aside about "escrow/APA as mocked buttons on a deal page".)
- The **E2E golden path extends to "sold"** once this lands (`testing_guide.md` §5).

### Post-MVP (when local is solid)

Stripe test mode + Stripe CLI forwarding webhooks to a FastAPI endpoint → real subscription gating · listing fees · swap SQLite → Postgres (change the connection string, add Alembic migrations) · deploy **single-origin under one domain** (reverse proxy routes `/api/*` + `/ws/*` to the FastAPI container, everything else to the SPA build — the production twin of the §3.4 Vite proxy, Baton-style) · then the agentic layer from `agentic_scope.md` — **which is where the FastAPI choice pays off**: the agents (LLM SDKs, tool-calling, MCP servers) are Python code living in the same service as your API and database.

---

## Part 5 — Mental Model Cheat-Sheet

| When you think…                   | The answer in this architecture is…                                                                    |
| --------------------------------- | ------------------------------------------------------------------------------------------------------ |
| "Where is the data?"              | SQL tables via SQLModel (files in `uploads/`, their paths in the DB)                                   |
| "Who may touch the data?"         | FastAPI permission dependencies — **the API is the only door**; the browser never sees the DB          |
| "Where does _trusted_ logic run?" | FastAPI endpoints & services (status transitions, fees, notifications)                                 |
| "How does the UI update live?"    | WebSockets for chat; refetch/polling for the rest (upgrade path: SSE)                                  |
| "How do I know who the user is?"  | JWT issued at login, decoded by the `get_current_user` dependency                                      |
| "Where's the business workflow?"  | `status` columns — state machines on listings, offers, access requests; transitions only via endpoints |
| "What about payments/KYC/escrow?" | Third-party vendors behind FastAPI routes + webhooks; mocked locally with the same state shapes        |
| "How do I see what's happening?"  | `/docs` Swagger UI + a SQLite browser + your `track()` console logs                                    |

The single most valuable thing to internalize from this whole project: **the marketplace is a set of state machines (listing, access, offer, deal) + rules about who can move them + realtime views of their current state.** Everything else — React, MUI, FastAPI itself — is replaceable plumbing around that idea.

---

## Part 6 — Alternative: Supabase *(moved — see `research/supabase_alternative.md`)*

> **Moved 2026-07-16.** The no-custom-backend alternative is now **[`research/supabase_alternative.md`](./research/supabase_alternative.md)** (sections renumbered 6.x → 1–7; content unchanged).
>
> **Status: considered and rejected, kept as reference** (constitution Article 1). The stack is decided — the FastAPI backend of Parts 3–4 — and **Milestone 0 has shipped on it**, so the old "pick one approach before Milestone 0" instruction is retired. Don't mix the two.
