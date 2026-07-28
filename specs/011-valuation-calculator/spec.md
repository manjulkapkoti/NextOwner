# Spec 011 — M11: Valuation calculator (lead magnet)

> **Milestone:** M11 — `docs/design_implementation.md` Part 4 § *Milestone 11 — Valuation calculator (F12)*: "Public page … inputs (type, MRR/revenue, profit, growth, churn) → multiple lookup table → estimated range with a friendly explanation. (No backend needed — **or make it your first fun `POST /valuation` endpoint if you prefer**.) *Business lesson:* this is a lead magnet — on the real site it captures seller emails before they list."
> **Not on the security-critical list** (`docs/security.md` §7 M11 — the crown-jewel list is M1/M2/M3/M5/M7/M8/M10). **But this milestone adds three routes, a response model, a new table holding PII, and a new `permissions.py`-gated admin surface, so `scripts/check_appsec_trigger.py` is expected to fire and an independent `appsec-engineer` pass is expected to run** — the list is a floor, the diff decides (constitution Article 3 §3). `security.md` §7's M11 line reads: *"pure client calc; if a `POST /valuation` endpoint is added, validate inputs and keep it injection-safe; no data exposure."* D1 below takes the endpoint option, so that conditional is now binding, not hypothetical.
> **Scope fold-ins read at spec time** (`docs/milestones.md` § Scope fold-ins → M11): *"**email lead capture** (FR-23's business half — the calculator exists to capture seller leads) — or explicitly de-scope it in the spec."* **It is in scope** (§4 D2). De-scoping it would leave FR-23 half-delivered with no milestone owning the other half, which is exactly the pattern M5's deferral note and M8's re-sequencing note were written to prevent.

---

## 1. What this milestone is

A public, unauthenticated page where somebody who owns a small internet business can type five numbers and immediately see what it might be worth — and then, if they want the estimate in writing, leave an email address. It is the marketplace's front door for the scarce side of the market: **supply**. Every other milestone so far serves people who already signed up; this one exists to create them.

Structurally it is the *inverse* of every milestone since M1. There is no owner, no counterparty, no state machine, and nothing to authorize on the two public routes — the trust question is not "may this caller see this row?" but "**can this route be made to cost us something, or to say something it shouldn't?**". So the whole security surface is input validation, rate limiting, response shaping, and the fact that the one table it writes holds an email address belonging to somebody who is not yet a user.

Two things follow from that, and they drive the decisions below:

- **The one privileged surface is the admin's read of the captured leads** (D3). It is the milestone's only `permissions.py` gate, and the only route where "wrong identity → 403" is even a question.
- **The calculation is server-owned** (D1). Not because a browser can't multiply, but because the multiples are *published business policy* (FR-23's words), the lead row must record a number we computed rather than one the client claimed, and a second implementation in TypeScript would drift from the first the week after it shipped.

## 2. FR references

| FR / F | What this milestone owes it |
|---|---|
| **FR-23** | "Valuation tool: public form computes an estimate from revenue/profit/growth/churn using published multiples; **captures email as a lead**." Both halves, in one milestone. |
| **F12** (`docs/requirements.md` §1) | "Rule-of-thumb valuation calculator (multiple × revenue/profit)" — MVP feature, "great lead magnet, simple to build." |
| **FR-21** (partial) | "Admin dashboard: … metrics." The admin lead list (D3) is one row of that dashboard, not a claim to have delivered FR-21. |

## 3. User stories

- As a **prospective seller** who has never heard of NextOwner, I want to get a rough valuation of my business in under a minute without signing up, so that I have a reason to trust this site with anything bigger.
- As a **prospective seller**, I want to understand *why* the number is what it is, so that I can tell whether the estimate is worth acting on rather than being handed an unexplained figure.
- As a **prospective seller**, I want to leave my email and get the estimate on record, so that I can come back to it when I'm actually ready to sell.
- As an **admin**, I want to see the leads the calculator has captured, so that the lead magnet is a funnel rather than a write-only table.
- As **any visitor**, I want the tool to tell me plainly that this is an estimate and not advice, so that I don't mistake a rule of thumb for a valuation.

## 4. Decisions

- **D1 — The calculation lives on the server, and *only* on the server.** `design_implementation.md` offers both ("no backend needed — or make it your first fun `POST /valuation` endpoint if you prefer"); this spec takes the endpoint. Three reasons, in order of weight: **(a)** FR-23 says the estimate uses *published multiples* — a pricing policy that must be changeable without a client redeploy, and auditable in one place; **(b)** D2's lead row stores the estimate, and a stored number the client supplied is a client-trusted value in a persisted record, which Article 2 #4 forbids on principle even where the value is harmless; **(c)** one implementation cannot disagree with itself — a TS copy for instant feedback plus a Python copy for the lead row is two sources of truth for the same business rule, and `docs/security.md`/the constitution have a standing preference against exactly that shape. **Accepted cost:** the estimate needs a round trip, so the UI is *"fill in the form → press Calculate"* rather than a figure that animates as you type. That is also the better conversion surface (a deliberate submit is the moment the email ask makes sense), so the cost is small and mostly notional.
- **D2 — Lead capture is in scope, and lives on a *separate* route from the calculation.** `POST /api/valuation` computes and **persists nothing**; `POST /api/valuation/leads` persists an email plus the inputs plus a **server-recomputed** estimate. Splitting them is the whole security design of this milestone: the route everyone hits stores no data and holds no PII, so the anonymous traffic surface cannot become a storage-exhaustion or PII-collection surface; the route that writes is a different key space with a much harder rate limit (D8), and is only ever reached by somebody who typed an address. A single combined route with an optional `email` field would put the write path one JSON field away from every anonymous request.
- **D3 — `GET /api/admin/valuation-leads` (behind `require_admin`) ships in this milestone.** A captured lead nobody can read is not a captured lead — and this codebase has a recorded lesson about tables written five milestones before their only consumer (`milestones.md` § Scope fold-ins → M8: *"a table designed five milestones before its only consumer is speculative, and one written by M3 but read by nobody until M8 could not be verified by any test writable at M3 time"*). The read route is deliberately minimal — a paginated, newest-first list — and reuses the existing `require_admin` gate rather than inventing a boundary. It does **not** claim to deliver FR-21's dashboard; it makes FR-23's second half verifiable.
- **D4 — No new `permissions.py` function.** Every other milestone since M1 added one. This one genuinely has no new trust boundary: two routes are public by design, and the third asks a question `require_admin` already answers ("is this caller an admin, re-read from the DB?"). Inventing `get_valuation_lead(...)` for a route that is a whole-table list, with no per-row ownership, would be ceremony that makes the codebase's one-function-per-boundary rule mean less, not more. **Recorded explicitly so a reviewer can see the absence was decided, not forgotten.**
- **D5 — The model: a per-type multiple band, applied to profit when the business is profitable and to revenue when it is not, adjusted by growth and churn, then clamped and rounded.** Fully specified in §6 so every number in the table tests is derivable from this spec rather than from the implementation. Three properties matter more than the specific constants: it is **deterministic** (same inputs → same output, no randomness, no time dependence), it is **total** (every input that passes validation produces an estimate — no input combination raises), and it is **monotonic in the obvious direction** (more profit never lowers the estimate; more churn never raises it). Those three are asserted as tests; the constants themselves are business policy and may be tuned later without breaking them.
- **D6 — Money is `Decimal` end to end, never `float`.** The M2 fold-in's rule (`Money` TypeDecorator, exact decimals) applies to a route that multiplies money by a multiple. Multipliers are `Decimal` too; the result is quantized to the nearest whole currency unit (§6.5). A float would produce estimates ending in `.30000000000000004` on a public marketing page.
- **D7 — The response is uniform whether or not the address is already a lead.** `POST /api/valuation/leads` always returns 201 with the estimate. There is **no unique constraint on `email`** and **no 409**: a duplicate-detecting response would turn the lead form into an email-enumeration oracle ("is this address already known to NextOwner?"), which is the same rule M1's login and M8's forgot-password already follow (`security.md` §7 M1/M8, §6 "Enumeration"). Repeat submissions are bounded by the rate limit (D8), not by a distinguishable error.
- **D8 — Both public routes are rate-limited per IP, at deliberately different caps.** Calculation: `valuation_rate_limit_max` (default **30 / minute**) — a real visitor tries a handful of scenarios in a sitting, and the route does arithmetic on validated numbers, so the cap is a DoS bound, not a business one. Lead capture: `valuation_lead_rate_limit_max` (default **5 / hour**) — it writes a PII row per call, so the cap is what stops the table becoming an open write endpoint. Both use pre-011's `enforce_per_ip` and are counted **before any work**, per pre-011 R1. The limits are per-instance today, with the same recorded caveat every other limiter in this codebase carries (`ratelimit.py` module docstring).
  **One correction to the record while doing it:** `specs/pre-011-rate-limiting/spec.md` describes M11 as *"an unauthenticated form that causes outbound email"* — the worst-case it was written to pre-empt. What this milestone actually ships sends no email (§8), so the lead route stores a row rather than mailing a stranger. Pre-011's reasoning still lands and its limiter still applies; only the severity is lower than forecast. Noted here rather than edited there, because pre-011's spec is an accurate record of what was believed when the decision was made.
- **D9 — A lead is not an audit row and gets no event table.** Constitution Article 2 #5's test — *"what does it preserve that the row itself loses?"* — returns nothing here: a lead has no state machine, nothing overwrites it, and it is never used to justify a decision about anybody. It is a marketing artifact. (Same shape as M8's ruling that a projection must never become an audit row, applied to a different kind of row.)
- **D10 — Erasure: a lead is hard-deleted, never anonymized.** `docs/data_protection.md` §3 asks the cascade-or-anonymize question per child table. `ValuationLead` has no FK to `user` (a lead is by definition somebody who is *not* a user yet) and no other row references it, so anonymizing in place would leave a row of business inputs attached to a tombstone with no evidentiary purpose. Erasure for a lead = delete the rows matching the address. The address is **never logged** and never carried in an analytics event (§7).
- **D11 — The result carries a disclaimer, generated server-side.** `agentic_scope.md` §Liability: *"valuation/legal outputs are decision support, not advice."* That constraint was written for the future agent, but it binds the static calculator for the same reason — a number on a page that somebody prices a life's work against. The disclaimer is part of the API response (not only the UI chrome) so it cannot be lost by a client that renders the number and drops the caveat.
- **D12 — `type` is a closed whitelist; an unknown type is 422, never a silent default.** The five values (`saas`, `ecommerce`, `content`, `agency`, `marketplace`) are the vocabulary already in `seed/seed.py`. Falling back to a default band for an unrecognized type would quietly attach a SaaS multiple to anything — a wrong answer presented with full confidence. Note the deliberate asymmetry with `Listing.type`, which is a free string: the calculator's table is *keyed* on the type, so an unknown key has no answer, whereas a listing's type is only ever displayed and filtered on.
- **D13 — No new MobX store.** The page holds a form, a result, and an error — all of it lives and dies with the page, is shared with nothing, and survives no navigation. `SavedSearches` and `AdminQueue` already set the precedent for component-local state on this kind of surface; a store would be state with no second reader.

## 5. Acceptance criteria

> Each line below becomes **exactly one test** (constitution Article 3 §2), written failing first. Group letters: **V** the valuation model · **C** the calculate route · **L** lead capture · **A** the admin lead list · **S** security & abuse · **X** errors & failure modes · **U** UI.

### V — The valuation model (F12, FR-23; `docs/testing_guide.md` §5 M11: *"Unit table-test … (type, revenue, profit, churn) → expected range, incl. edge cases"*)

- **V1** — GIVEN the table of representative cases in §6.6, WHEN `estimate_valuation` is called with each row's inputs, THEN it returns that row's exact `low`/`high`/`driver`. *(One parametrized table test — the checklist's ☐, and the only criterion here that maps to a multi-case test by design.)*
- **V2** — GIVEN a profitable business (`ttm_profit > 0`), WHEN the estimate is computed, THEN `driver == "profit"` and the range is derived from `ttm_profit`, not `ttm_revenue`.
- **V3** — GIVEN a business with **zero** profit and positive revenue, WHEN the estimate is computed, THEN `driver == "revenue"` and the range is derived from `ttm_revenue` (the checklist's "zero profit" edge case).
- **V4** — GIVEN a business with **negative** profit (a loss) and positive revenue, WHEN the estimate is computed, THEN `driver == "revenue"` — a loss-making business is valued on revenue, and the returned range is never negative.
- **V5** — GIVEN both `ttm_revenue` and `ttm_profit` are zero, WHEN the estimate is computed, THEN `low == high == 0`, `driver == "none"`, and the explanation says there is not enough signal to estimate — the route still returns 200 rather than erroring on an input that is valid but uninformative.
- **V6** — GIVEN two otherwise identical inputs differing only in `ttm_profit`, WHEN both are computed, THEN the higher profit yields a `low` and `high` that are each `>=` the lower one's (monotonicity in profit — D5).
- **V7** — GIVEN two otherwise identical SaaS inputs differing only in `churn_pct`, WHEN both are computed, THEN the higher churn yields a `low` and `high` that are each `<=` the lower one's (monotonicity in churn — D5).
- **V8** — GIVEN two otherwise identical inputs differing only in `growth_pct`, WHEN both are computed, THEN the higher growth yields a `low` and `high` that are each `>=` the lower one's (monotonicity in growth — D5).
- **V9** — GIVEN churn well past the point the model can meaningfully price (e.g. `churn_pct = 95`, the checklist's "absurd churn"), WHEN the estimate is computed, THEN it returns a non-negative range with the churn factor **clamped** at its floor (§6.4) rather than producing a negative or zero-collapsed multiple.
- **V10** — GIVEN growth far past any plausible band (e.g. `growth_pct = 900`), WHEN the estimate is computed, THEN the growth factor is **clamped** at its ceiling (§6.4) — an extreme claimed growth rate cannot inflate the estimate without bound.
- **V11** — GIVEN any valid input, WHEN the estimate is computed, THEN `low <= high` and both are `Decimal` quantized to whole units (D6, §6.5) — no float artifacts, no inverted range.
- **V12** — GIVEN the same inputs computed twice, WHEN both results are compared, THEN they are identical (determinism — D5; no clock, no randomness).
- **V13** — GIVEN each of the five whitelisted types with otherwise identical inputs, WHEN each is computed, THEN each returns the band for **its own** type (proving the lookup is keyed, not defaulted — D12).

### C — `POST /api/valuation` (the public calculate route)

- **C1** — GIVEN an anonymous visitor (no `Authorization` header), WHEN they `POST /api/valuation` with valid inputs, THEN 200 with `low`, `high`, `driver`, `explanation`, and `disclaimer`.
- **C2** — GIVEN a valid request, WHEN the response is inspected, THEN the numbers match `estimate_valuation` for the same inputs — the route computes via the shared module and does not reimplement the model.
- **C3** — GIVEN a valid request, WHEN it completes, THEN **no row is written to any table** (D2 — the calculate route persists nothing; asserted by counting `ValuationLead` rows before and after).
- **C4** — GIVEN a valid request, WHEN the response is inspected, THEN `disclaimer` is present and non-empty (D11).
- **C5** — GIVEN a request omitting the optional fields (`growth_pct`, `churn_pct`), WHEN it is sent, THEN 200 — the optional inputs default to neutral factors rather than being required.

### L — `POST /api/valuation/leads` (lead capture — FR-23's second half, the M11 fold-in)

- **L1** — GIVEN an anonymous visitor, WHEN they `POST /api/valuation/leads` with a valid email and valid inputs, THEN 201, one `ValuationLead` row exists, and the response carries the same estimate shape the calculate route returns.
- **L2** — GIVEN a lead submission, WHEN the stored row is inspected, THEN its `low`/`high` are the **server's** recomputation of the submitted inputs — not any value present in the request body (D2, Article 2 #4). *(Paired with S5, which sends a conflicting value.)*
- **L3** — GIVEN the same email submitting twice with different inputs, WHEN both are sent, THEN both return 201 and **two** rows exist — a lead is an append-only capture event with no unique constraint (D7).
- **L4** — GIVEN a lead submission, WHEN the stored row is inspected, THEN it carries the submitted `type`, `ttm_revenue`, `ttm_profit`, `growth_pct`, `churn_pct` and a `created_at` timestamp.

### A — `GET /api/admin/valuation-leads` (D3)

- **A1** — GIVEN an admin and several captured leads, WHEN they `GET /api/admin/valuation-leads`, THEN 200 with all of them, **newest first**.
- **A2** — GIVEN more leads than the page cap, WHEN an admin lists them, THEN at most `valuation_leads_page_limit` rows are returned (the same pagination-cap control M4 and M8 apply — `security.md` §6 "DoS surface").
- **A3** — GIVEN no leads captured yet, WHEN an admin lists them, THEN 200 with an empty list (not 404).

### S — Security & abuse (`security.md` §7 M11 + §6)

> §7's M11 line: *"pure client calc; if a `POST /valuation` endpoint is added, **validate inputs and keep it injection-safe; no data exposure**."* D1 makes all three binding.

- **S1** — GIVEN a **non-admin authenticated** user, WHEN they `GET /api/admin/valuation-leads`, THEN 403 — the milestone's one privileged surface, wrong identity (`security.md` §8 "Permissions / a new route").
- **S2** — GIVEN an **unauthenticated** visitor, WHEN they `GET /api/admin/valuation-leads`, THEN 401.
- **S3** — GIVEN a user whose `is_admin` was flipped **off in the database** after their token was issued, WHEN they present that still-valid token to `GET /api/admin/valuation-leads`, THEN 403 — the role is re-read from the DB, never taken from the token (`security.md` §8 "Auth").
- **S4** — GIVEN a `POST /api/valuation` body carrying extra server-owned-looking fields (`low`, `high`, `driver`, `disclaimer`, `id`, `is_admin`), WHEN it is sent, THEN they are ignored and the response is computed from the legitimate inputs alone — mass-assignment is impossible **by schema**, because the request model has no such fields (`security.md` §8 "Create / PUT").
- **S5** — GIVEN a `POST /api/valuation/leads` body carrying a **client-supplied `low`/`high`** far from the true estimate, WHEN it is sent, THEN the stored row and the response carry the server's numbers and the client's are discarded (the persisted half of S4 — Article 2 #4).
- **S6** — GIVEN a `type` containing a SQL-injection payload (`saas'; DROP TABLE valuationlead;--`), WHEN it is sent to either public route, THEN 422 from the whitelist (D12) and the `valuationlead` table still exists — injection-safe both by parameterized queries and by the value never reaching a query at all.
- **S7** — GIVEN an `email` containing a script payload (`<script>alert(1)</script>@x.com`), WHEN it is sent to the lead route, THEN 422 from `EmailStr` — the address is validated at the boundary, before it is ever stored or shown to an admin.
- **S8** — GIVEN a lead captured from an anonymous visitor, WHEN the calculate/lead **response models** are inspected, THEN neither exposes any field of any other table — no listing, no user, no id of another row (`security.md` §8 "Data exposure / public route"; §7's "no data exposure").
- **S9** — GIVEN an authenticated user calls `POST /api/valuation` **with** a valid token, WHEN the response is compared to the anonymous one for the same inputs, THEN they are identical and no identity is recorded — a token present on a public route must not widen behavior or silently attribute the lead (the S8-shaped rule spec 004 applied to browse).
- **S10** — GIVEN the calculate limiter's cap, WHEN one IP exceeds it, THEN 429 with a `Retry-After` header and the generic rate-limited body (D8; pre-011's contract).
- **S11** — GIVEN the lead limiter's much harder cap, WHEN one IP exceeds it, THEN 429 **and no further `ValuationLead` rows are written** — the refusal happens before the write, so the storage surface is actually bounded (D8, pre-011 R1).
- **S12** — GIVEN a lead is captured, WHEN the analytics event emitted for it is inspected, THEN it carries **no email address** and no other PII (`security.md` § Audit & logging; §7 lead-capture).

### X — Errors & failure modes (`docs/error_handling.md`)

> **There is no 409 in this milestone, and that is a finding, not an omission.** This is the first milestone since M1 with no state machine — nothing here transitions, so no transition can be illegal. Recorded so a reviewer running the §8 matrix does not look for a missing test.

- **X1** — GIVEN a negative `ttm_revenue`, WHEN `POST /api/valuation` is called, THEN 422 naming the offending field.
- **X2** — GIVEN `churn_pct` above 100 (a monthly churn rate that is not a percentage), WHEN either public route is called, THEN 422 — validated at the boundary, distinct from V9's clamping of a *valid but extreme* value.
- **X3** — GIVEN `ttm_profit` greater than `ttm_revenue`, WHEN either public route is called, THEN 422 — a cross-field invariant, enforced in the request model rather than absorbed silently by the model.
- **X4** — GIVEN `ttm_revenue` beyond the accepted ceiling (`valuation_max_amount`), WHEN either public route is called, THEN 422 — an unbounded numeric input is a request-size and arithmetic surface like any other (`security.md` §2 "validate every input at the boundary").
- **X5** — GIVEN a missing required field (`type`, `ttm_revenue`, or `ttm_profit`), WHEN either public route is called, THEN 422.
- **X6** — GIVEN a malformed `email` on the lead route, WHEN it is sent, THEN 422 and **no row is written**.
- **X7** — GIVEN a forced internal error inside the valuation router, WHEN a route is called, THEN the generic 500 contract (`detail`, `request_id`) is returned with no stack trace, SQL, or internal detail (reuses the M1 global handler — no new code, one new test).
- **X8** — GIVEN any 4xx from these routes, WHEN the body is inspected, THEN it carries the `{detail, code}` shape and leaks no internal detail (`error_handling.md` §1).

### U — UI (`app/`)

- **U1** — GIVEN a logged-out visitor, WHEN they navigate to `/valuation`, THEN the form renders without a redirect to login — the page is public, like `/browse` (spec 004 F9).
- **U2** — GIVEN a filled-in form, WHEN the visitor submits, THEN the estimate range, the explanation, and the disclaimer are all rendered.
- **U3** — GIVEN a request in flight, WHEN the component renders, THEN a loading state is shown and the submit control is disabled (no double-submit).
- **U4** — GIVEN the API returns 422, WHEN the component renders, THEN the field-level message is shown inline next to the offending input rather than as a generic banner (`error_handling.md` §3).
- **U5** — GIVEN the API returns 429, WHEN the component renders, THEN a plain "you're going too fast, try again shortly" message is shown — not a raw error code.
- **U6** — GIVEN a result on screen, WHEN the visitor submits the email-capture form, THEN a confirmation replaces the form and the estimate stays visible.
- **U7** — GIVEN the page has never been submitted, WHEN it first renders, THEN the result area shows an empty/initial state rather than a zeroed estimate that looks like an answer.
- **U8** — GIVEN any authenticated or anonymous visitor, WHEN the nav renders, THEN a link to the calculator is present (the lead magnet has to be reachable to be a lead magnet).

## 6. The model, fully specified

> Everything in this section is **normative** — the V-group table tests derive their expected values from here, not from the code. Constants are business policy and may be re-tuned later; the *shape* (band → driver → factors → clamp → round) is the design.

### 6.1 Inputs

| Field | Type | Required | Bounds |
|---|---|---|---|
| `type` | one of `saas`, `ecommerce`, `content`, `agency`, `marketplace` | yes | closed whitelist (D12) |
| `ttm_revenue` | `Decimal` | yes | `0 <= x <= valuation_max_amount` |
| `ttm_profit` | `Decimal` | yes | `-valuation_max_amount <= x <= ttm_revenue` (X3) |
| `growth_pct` | `Decimal` | no (default `0`) | `-100 <= x <= 1000` (annual revenue growth, %) |
| `churn_pct` | `Decimal` | no (default `0`) | `0 <= x <= 100` (monthly customer churn, %) |

`mrr` is **not** an input. Part 4's sketch lists "MRR/revenue" as alternatives, and asking for both invites a visitor to enter a monthly figure in an annual field — the single worst input error this form can make, and one no validation can detect. TTM revenue is the figure every multiple in §6.2 is expressed against.

### 6.2 Bands (multiple, low–high)

| `type` | profit multiple | revenue multiple |
|---|---|---|
| `saas` | 3.0 – 5.0 | 2.0 – 4.0 |
| `marketplace` | 3.0 – 5.0 | 2.0 – 4.0 |
| `content` | 2.5 – 4.0 | 1.5 – 3.0 |
| `ecommerce` | 2.0 – 3.5 | 0.6 – 1.2 |
| `agency` | 1.5 – 2.5 | 0.5 – 1.0 |

### 6.3 Driver selection

- `ttm_profit > 0` → **profit** driver: band = the profit multiple, base = `ttm_profit`.
- `ttm_profit <= 0` **and** `ttm_revenue > 0` → **revenue** driver: band = the revenue multiple, base = `ttm_revenue`.
- both zero → **none**: `low = high = 0` (V5).

### 6.4 Adjustment factors (each clamped, then multiplied together, then the product clamped)

- **growth factor** = `1 + clamp(growth_pct, -50, 100) / 200` → spans `0.75 … 1.50`.
- **churn factor** = `1 - clamp(churn_pct, 0, 20) / 40` → spans `1.00 … 0.50`.
- **combined** = `clamp(growth_factor * churn_factor, 0.50, 1.75)`.

The inner clamps are what make V9/V10 true: an absurd input is *ignored past the band edge*, not extrapolated. The outer clamp bounds the pathological corner where both factors are extreme in the same direction.

### 6.5 Result

- `low  = round_to_unit(base * band_low  * combined)`
- `high = round_to_unit(base * band_high * combined)`
- `round_to_unit` quantizes to whole currency units, `ROUND_HALF_UP`, as `Decimal` (D6).
- `low <= high` always (the band guarantees it; asserted by V11).
- `explanation` — a server-generated sentence naming the driver, the band, and any factor that moved the number.
- `disclaimer` — a fixed server-owned string (D11).

### 6.6 Representative cases (the V1 table)

| # | `type` | `ttm_revenue` | `ttm_profit` | `growth_pct` | `churn_pct` | driver | low | high |
|---|---|---|---|---|---|---|---|---|
| 1 | `saas` | 200000 | 100000 | 0 | 0 | profit | 300000 | 500000 |
| 2 | `saas` | 200000 | 100000 | 100 | 0 | profit | 450000 | 750000 |
| 3 | `saas` | 200000 | 100000 | 0 | 20 | profit | 150000 | 250000 |
| 4 | `saas` | 200000 | 0 | 0 | 0 | revenue | 400000 | 800000 |
| 5 | `saas` | 200000 | −50000 | 0 | 0 | revenue | 400000 | 800000 |
| 6 | `agency` | 200000 | 100000 | 0 | 0 | profit | 150000 | 250000 |
| 7 | `ecommerce` | 200000 | 100000 | 0 | 0 | profit | 200000 | 350000 |
| 8 | `content` | 200000 | 100000 | 0 | 0 | profit | 250000 | 400000 |
| 9 | `marketplace` | 200000 | 100000 | 0 | 0 | profit | 300000 | 500000 |
| 10 | `saas` | 0 | 0 | 0 | 0 | none | 0 | 0 |
| 11 | `saas` | 200000 | 100000 | 900 | 95 | profit | 225000 | 375000 |
| 12 | `saas` | 200000 | 100000 | 100 | 20 | profit | 225000 | 375000 |

*(Row 11 is the both-extremes case: growth clamps to +100 → 1.50, churn clamps to 20 → 0.50, product 0.75, inside the outer clamp. Row 12 reaches the same factor from valid-but-unclamped inputs — the pair proves the clamp is doing the work in 11.)*

## 7. Analytics events

- `valuation_calculated` — props: `type`, `driver`. **No amounts, no email, no identity.**
- `valuation_lead_captured` — props: `type`. **No email** (S12).

## 8. Out of scope

- **Comps from real closed deals.** The estimate is a published rule of thumb, not a data-driven comp. Upgrading it to pull from the platform's own closed-deal corpus is `agentic_scope.md` proposal F, and needs M12's `sold` rows to exist first.
- **Charts.** `docs/design_system_spec.md` notes charts "(M11+)" — the range is rendered as text and a simple bar, with no charting library added. The design-system note says *at or after* M11, not *in* it.
- **Emailing the lead.** M8 owns the email channel and would make this a one-line add, but sending unsolicited mail to an address captured on a public form is a policy decision (consent, unsubscribe, CAN-SPAM/GDPR) that belongs to `legal-compliance`, not to a build milestone. The address is captured and readable by an admin; nothing is sent.
- **Linking a lead to a user account.** A lead is anonymous by construction (D10). Reconciling a lead with the account that later signs up with the same address is a CRM concern, not an MVP one.
- **Admin lead management** — editing, deleting, exporting, or marking a lead as contacted. The admin surface is read-only (D3).
- **Prefilling the listing wizard from a calculation.** An obvious conversion win and a tempting one-liner; deliberately deferred so this milestone's public routes never need to know about a session.
