# Plan 011 — M11: Valuation calculator (lead magnet)

> Implementation plan for [`spec.md`](./spec.md). Every section except **Build order** describes *what exists when this milestone is done*; Build order describes *the order it gets built in*.

---

## Schema deltas (`backend/app/models.py`)

One new table. Nothing else in the data model changes.

```python
class ValuationLead(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True)          # PII — see § Data protection
    type: str
    ttm_revenue: Decimal = Field(sa_type=Money)
    ttm_profit: Decimal = Field(sa_type=Money)
    growth_pct: Decimal = Field(sa_type=Money)
    churn_pct: Decimal = Field(sa_type=Money)
    estimate_low: Decimal = Field(sa_type=Money)     # server-computed (spec L2/S5)
    estimate_high: Decimal = Field(sa_type=Money)
    driver: str                                       # "profit" | "revenue" | "none"
    created_at: datetime = Field(default_factory=_utcnow, index=True)
```

- **`email` is indexed but has NO unique constraint** — deliberate (spec D7). A unique constraint would produce a distinguishable duplicate error, turning the form into an email-enumeration oracle.
- **No `user_id` FK.** A lead is somebody who is not a user yet (D10). Adding the FK "just in case" would create the identity linkage S9 exists to prevent.
- **Money columns use the existing `Money` `TypeDecorator`** — exact `Decimal`, never float (D6). `growth_pct`/`churn_pct` reuse it for the same reason `Listing.churn_pct` does.
- **`created_at` is indexed** because the admin list's only ordering is newest-first (A1) and its only bound is a page cap (A2).

## New module (`backend/app/valuation.py`)

The model from spec §6, as a pure function with no DB, no request, and no clock:

```python
ValuationType = Literal["saas", "ecommerce", "content", "agency", "marketplace"]

PROFIT_BANDS:  dict[str, tuple[Decimal, Decimal]]   # §6.2
REVENUE_BANDS: dict[str, tuple[Decimal, Decimal]]

@dataclass(frozen=True)
class Estimate:
    low: Decimal
    high: Decimal
    driver: Literal["profit", "revenue", "none"]
    explanation: str

def estimate_valuation(*, type, ttm_revenue, ttm_profit, growth_pct, churn_pct) -> Estimate
```

Its own module rather than a helper inside the router, for the reason D1 gives: the bands are business policy with one home. Being pure is what makes the V-group a table test with no fixtures (`testing_guide.md` §5 M11's ☐).

## Endpoints

| Method + path | Auth / gate | Writes | Notes |
|---|---|---|---|
| `POST /api/valuation` | **none** (public) | nothing (C3) | `enforce_per_ip(_valuation_limiter)` first, before any work (D8, pre-011 R1) |
| `POST /api/valuation/leads` | **none** (public) | one `ValuationLead` | `enforce_per_ip(_valuation_lead_limiter)` first (S11); recomputes the estimate server-side (L2/S5) |
| `GET /api/admin/valuation-leads` | `require_admin` | — | newest-first, capped at `valuation_leads_page_limit` (A1–A3) |

No state transitions anywhere in this milestone — hence no 409 (spec §5 X preamble).

Router placement: the two public routes live in a new `backend/app/routers/valuation.py` (mounted `prefix="/api"`); the admin read is added to the **existing** `routers/admin.py`, beside `admin_listings`, because that file is already "the routes behind `require_admin`" and a second admin router would split one boundary across two files.

## Permission gates

**None added** (spec D4 — recorded as a decision, not an oversight). The admin route reuses `require_admin`, which re-reads `is_admin` from the DB (S3). The two public routes are unauthenticated by design and never read the caller's identity at all — the property S9 asserts, mirroring `browse_listings`' "no widening if a token is present."

## Response models (`backend/app/schemas.py`)

```python
class ValuationRequest(SQLModel)      # type, ttm_revenue, ttm_profit, growth_pct?, churn_pct?
class ValuationLeadCreate(ValuationRequest)   # + email: EmailStr
class ValuationEstimateRead(BaseModel)        # low, high, driver, explanation, disclaimer
class ValuationLeadRead(BaseModel)            # the admin row
```

- `ValuationRequest` lists **only** the five inputs — so `low`, `high`, `driver`, `id`, `is_admin` have no field to bind to and mass-assignment is impossible *by schema*, not by runtime filtering (S4/S5, `security.md` §6).
- Bounds live on the fields (`ge`/`le`) plus one `model_validator` for the cross-field `ttm_profit <= ttm_revenue` rule (X3), so every X-group failure is a Pydantic 422 with a field name.
- `ValuationEstimateRead` is a **standalone** model referencing no ORM row — it cannot leak a field of another table because it has no relationship to one (S8). Same construction rule `WatchlistEntryRead` follows: built field by field, never spread from a row.
- `ValuationLeadRead` carries `email` and is returned **only** by the `require_admin` route.

## Frontend (`app/src/`)

- **`components/ValuationCalculator.tsx`** — the whole page: the input form, the result card (range, explanation, disclaimer), and the email-capture form that appears once there is a result. Component-local `useState` for form/result/error/loading — **no new MobX store** (D13).
- **`App.tsx`** — a public `/valuation` route, alongside `/browse` and outside `RequireAuth` (U1).
- **`components/NavBar.tsx`** — a link to the calculator (U8).
- **`components/LandingPage.tsx`** — a CTA into it. The landing page's audience is the seller side, which is exactly this tool's audience.
- **`lib/api.ts`** — no change: both public calls go through the existing `publicApi` entry point, which never attaches the JWT and never emits `auth:unauthorized`. That is the client-side half of S9. *(`publicApi` currently issues GETs only; it takes an options argument for POST bodies in the same shape `api()` already uses — a widening of one function, not a new client.)*

## Errors

| Condition | Status | Mechanism |
|---|---|---|
| Bad/missing/out-of-range input, bad email | 422 | Pydantic field + `model_validator` (X1–X6) |
| Rate limit exceeded | 429 + `Retry-After` | `enforce_per_ip` → existing `RateLimited` (S10, S11) |
| Non-admin / anonymous on the admin route | 403 / 401 | existing `require_admin` / `get_current_user` (S1–S3) |
| Anything unhandled | 500 generic | existing `main.py` catch-all (X7) |

**No new `AppError` subclass.** Nothing in this milestone fails in a way the existing hierarchy does not already name — worth stating, because adding one per milestone by habit is how an error contract stops being a contract.

Frontend states (`error_handling.md` §3): initial/empty (U7), loading with the submit disabled (U3), inline field-level 422 (U4), a plain-language 429 (U5), and a generic fallback for anything else.

## Analytics events

- `valuation_calculated` — `{ type, driver }`
- `valuation_lead_captured` — `{ type }`

Neither carries an email, an amount, or an identity (S12; `security.md` § Audit & logging).

## Data protection (`docs/data_protection.md` §6)

- **New PII: one field — `ValuationLead.email`**, an address belonging to somebody who is not a user. Justified by FR-23 (the lead *is* the feature) and minimized to exactly that: no name, no company, no IP address stored. The business inputs stored beside it are self-reported figures about a business, not personal data.
- **Erasure: hard-delete rows matching the address** (D10). No anonymize-in-place, because nothing references a lead and an anonymized lead has no evidentiary value — contrast offers/access-requests, which §3 keeps for audit with the author anonymized.
- **The address is never logged** and never leaves the `require_admin` route.
- Checklist (§7): new person-referencing table ✔ has a defined erasure behavior; no PII on any public response model; no audit row copies the address (there is no audit row — D9).

## Config additions (`backend/app/config.py`)

```python
valuation_rate_limit_max: int = 30                   # per IP per minute (D8)
valuation_rate_limit_window_seconds: int = 60
valuation_lead_rate_limit_max: int = 5               # per IP per hour — this one writes
valuation_lead_rate_limit_window_seconds: int = 3600
valuation_leads_page_limit: int = 50                 # admin list cap (A2)
valuation_max_amount: Decimal = Decimal("1000000000")  # input ceiling (X4)
```

---

## Build order

> The implementation slices, in dependency order. **One trust boundary (or one structural seam) each; one Conventional Commit each.** No checkboxes and no status here by design — the **red test list is the status** (`cd backend && pytest -q --lf`), and the red count is the progress bar (constitution Article 3 §1).
>
> This milestone's slices are unusual in that only slice 5 involves a permission gate. The seam that replaces it as the organizing principle is **"what does this slice let an anonymous caller do?"** — which is why the pure model comes before any route, and the route that *writes* comes after the route that does not.

1. **Config + the pure model.** `config.py` additions, then `valuation.py`: bands, clamps, `estimate_valuation`. No FastAPI, no DB. **Turns green:** V1–V13. *Why first:* it is the only part of the milestone with no dependencies, and it is where every number the rest of the milestone reports comes from. Getting the table test green first means every later failure is a plumbing failure, never an arithmetic one.

2. **Request/response schemas + validation.** `ValuationRequest`, `ValuationLeadCreate`, `ValuationEstimateRead` with all bounds and the cross-field validator. **Turns green:** X1–X6, X8 (once slice 3 mounts a route to send them at — the validator tests that can run headless run here; the rest land with slice 3). *Why second:* the boundary that rejects hostile input must exist before the route that accepts it, not after. Writing it as a separate slice also keeps S4's "impossible by schema" claim honest — the request model is *designed* without those fields, rather than having them stripped later.

3. **`POST /api/valuation` — the public, non-writing route.** New router + `main.py` mount + the calculate limiter. **Turns green:** C1–C5, S4, S6, S9, S10, X7, and the remainder of the X group. *Why third:* it is the milestone's whole feature with none of its risk — it reads nothing, writes nothing, and authenticates nobody. Once it is green, everything left is about persistence and identity.

4. **`ValuationLead` + `POST /api/valuation/leads` — the writing route.** The model, the table, the lead limiter, and the server-side recomputation. **Turns green:** L1–L4, S5, S7, S11, S12. *Why here and not earlier:* this is the first slice where an anonymous request causes a row to exist. It deliberately lands *after* the limiter pattern is proven on the harmless route (slice 3), so the cap on the harmful one is applied by a mechanism that already has a passing test.

5. **`GET /api/admin/valuation-leads` — the one privileged surface.** Added to `routers/admin.py` behind `require_admin`, with the page cap. **Turns green:** A1–A3, S1–S3, S8. *Why last on the backend:* it is the only slice with a trust boundary, and it needs rows to exist (slice 4) before "wrong identity cannot read them" means anything. A 403 test against an empty table proves less than a 403 test against a table with somebody's email in it.

6. **The public page.** `ValuationCalculator.tsx`, the `/valuation` route, the `publicApi` POST widening, plus the nav link and the landing CTA. **Turns green:** U1–U8. *Why last:* the UI consumes an API contract that slices 3–5 fix. Building it earlier means building against a guess.

**No slice removes tests.** Nothing in this milestone supersedes an earlier deferral, and a `git grep -in "until M11\|defer.*M11\|M11 owns"` at spec time returns only forward-looking prose in `design_system_spec.md` ("Charts (M11+)"), which spec §8 explicitly declines rather than retires. If a slice turns up an expired deferral this scan missed, retire it in place with a dated note and say so in the commit — never a silent delete.
