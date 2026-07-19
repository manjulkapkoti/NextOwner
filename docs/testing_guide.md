# Testing Guide — Environment, Framework & Per-Milestone Tests (FastAPI stack)

> Companion to [`design_implementation.md`](./design_implementation.md). Each milestone in Part 4 has a matching test checklist here. **A milestone is "done" when its tests pass and all earlier tests still pass.** With spec-driven development, these tests ARE your acceptance criteria made executable — write them from the spec *before* implementing.

---

## 1. Testing Philosophy for This Project

A marketplace's biggest risks are not visual bugs — they are **trust failures**: a buyer reading private financials without an NDA, a seller publishing an unreviewed listing, a non-admin approving listings. In the FastAPI architecture, all of those live in **permission dependencies and endpoint logic** (`permissions.py`, the routers), so this project inverts the usual testing pyramid priority:

```
        ▲  E2E (Playwright)        — 1 golden-path script, added after Phase D
       ▲▲  Endpoint/workflow tests — every state transition, happy + forbidden paths
     ▲▲▲▲  PERMISSION TESTS        — the crown jewels; every 403/404 in the spec
   ▲▲▲▲▲▲  Unit + component tests  — pure logic (valuation, filters) and key components
```

The distinction between the top-middle rows is intent, not tooling — both use pytest + FastAPI's `TestClient`:
- **Permission tests** ask "*who* may do this?" → assert `403`/`401`/`404` for the wrong identity, `200` for the right one.
- **Workflow tests** ask "*what happens* when they do?" → assert status transitions, audit rows, side effects.

Rule of thumb: **every GIVEN/WHEN/THEN in a milestone spec becomes exactly one test.** If you can't write the test, the criterion was too vague — fix the spec.

A structural advantage of your stack: since the browser can never reach the database, testing the API **is** testing the security model. There is no separate rules engine to test — one door, one test surface.

---

## 2. The Test Stack

| Layer | Tool | Why |
|---|---|---|
| Backend test runner | **pytest** | The Python standard; terse tests, powerful fixtures |
| API testing | **FastAPI `TestClient`** (built on httpx, ships with `fastapi[standard]`) | Calls your app in-process — no server to start, real routing/auth/validation |
| Test database | **SQLite in-memory**, fresh per test, injected via `dependency_overrides` | Every test starts from a clean, empty DB in milliseconds |
| WebSocket tests | `TestClient.websocket_connect` | Chat is testable without a browser |
| Component tests | **Vitest + @testing-library/react** (jsdom) | Test what the user sees, not implementation details |
| E2E | **Playwright** | Drives a real browser against Vite + `fastapi dev` |

---

## 3. One-Time Setup (≈ 30 minutes)

### 3.1 Install

```bash
# Backend (inside backend/, venv active)
pip install pytest

# Component testing (inside app/)
cd app && npm i -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom && cd ..

# E2E (defer until Phase D)
npm init playwright@latest                    # choose e2e/ as the tests folder
```

### 3.2 Folder layout

```
NextOwner/
├── app/src/**/*.test.tsx        # unit + component tests, colocated with code
├── backend/tests/
│   ├── conftest.py              # shared fixtures: db, client, as_user, seed  ← write once
│   ├── test_auth.py             # M1
│   ├── test_listings.py         # M2, M4
│   ├── test_curation.py         # M3
│   ├── test_nda_gate.py         # M5  ← most important file in the project
│   ├── test_chat.py             # M6
│   ├── test_offers.py           # M7
│   ├── test_alerts.py           # M8
│   └── ...
└── e2e/golden-path.spec.ts
```

### 3.3 Run scripts — the "easy setup steps"

The **root** `package.json` runs everything from one place:

```json
{
  "scripts": {
    "test:api":  "node scripts/test-api.mjs",
    "test:unit": "npm run test --prefix app",
    "test:e2e":  "playwright test",
    "test":      "npm run test:api && npm run test:unit"
  }
}
```

`test:api` uses a tiny launcher (`scripts/test-api.mjs`) that finds the backend venv's Python on either layout (Windows `Scripts/`, POSIX `bin/`) and falls back to `python` on PATH (what CI uses) — so the root `npm test` works everywhere without activating the venv.

Day-to-day workflow:

```bash
npm test                          # backend + frontend tests, one command
cd backend && pytest -q           # fast loop while writing endpoints
cd backend && pytest tests/test_nda_gate.py -q    # a single file
cd backend && pytest -q -x --lf   # re-run only what failed last time
```

There is nothing to boot or tear down — the in-memory database is created and destroyed *inside each test* by the fixtures below. That's the whole trick.

### 3.4 `conftest.py` — write once, every test stays 5 lines

```python
# backend/tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.db import get_session

@pytest.fixture
def session():
    """A fresh, empty in-memory database for every single test."""
    engine = create_engine("sqlite://",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s

@pytest.fixture
def client(session):
    """TestClient whose get_session dependency is swapped for the test DB."""
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def as_user(client):
    """Register + log in a user through the real endpoints; returns auth headers."""
    def _login(email="user@test.com", role="buyer", admin=False):
        client.post("/api/auth/register",
                    json={"email": email, "password": "pw123456", "role": role})
        if admin:
            ...  # flip is_admin directly on the session — a seed helper, not an endpoint!
        tok = client.post("/api/auth/login",
                          data={"username": email, "password": "pw123456"}
                          ).json()["access_token"]
        return {"Authorization": f"Bearer {tok}"}
    return _login

@pytest.fixture
def seed(session, client, as_user):
    """Tiny factories so each test reads as one-line arrangement."""
    class Seed:
        def live_listing(self, owner="sara@test.com", **kw): ...
        def signed_nda(self, buyer): ...                 # stamps users.nda_signed_at
        def access_request(self, listing_id, buyer, status="requested"): ...
        def offer(self, listing_id, buyer, price=100_000): ...
    return Seed()
```

Two conventions worth keeping:
- **Go through the real endpoints wherever the product has one** (register, login, submit offer) — you're testing the same path production uses.
- **Reach into the `session` directly only for things no endpoint should ever do** (making someone admin, force-setting a status) — that's seeding, not cheating.

---

## 4. Anatomy of the Test Types (worked examples)

### 4.1 Permission test — the access gate (Milestone 5's core)

```python
# backend/tests/test_nda_gate.py

def test_unsigned_nda_cannot_create_access_request(client, as_user, seed):
    listing = seed.live_listing(owner="sara@test.com")
    bob = as_user("bob@test.com")                    # has NOT signed the platform NDA
    r = client.post(f"/api/listings/{listing.id}/access-request", headers=bob)
    assert r.status_code == 403

def test_buyer_without_access_is_denied_private_data(client, as_user, seed):
    listing = seed.live_listing(owner="sara@test.com")
    bob = as_user("bob@test.com")
    r = client.get(f"/api/listings/{listing.id}/private", headers=bob)
    assert r.status_code == 403

def test_requested_but_not_approved_is_still_denied(client, as_user, seed):
    listing = seed.live_listing(owner="sara@test.com")
    bob = as_user("bob@test.com")
    seed.signed_nda("bob@test.com")
    seed.access_request(listing.id, buyer="bob@test.com", status="requested")
    assert client.get(f"/api/listings/{listing.id}/private", headers=bob).status_code == 403

def test_approved_buyer_is_allowed(client, as_user, seed):
    listing = seed.live_listing(owner="sara@test.com")
    bob = as_user("bob@test.com")
    seed.signed_nda("bob@test.com")
    seed.access_request(listing.id, buyer="bob@test.com", status="approved")
    r = client.get(f"/api/listings/{listing.id}/private", headers=bob)
    assert r.status_code == 200
    assert "company_name" in r.json()
```

Every permission test follows this exact shape: **seed → act as a specific identity → assert status code.** Copy-paste and vary.

### 4.2 Workflow test — curation (Milestone 3)

```python
# backend/tests/test_curation.py

def test_non_admin_cannot_approve(client, as_user, seed):
    listing = seed.live_listing(status="pending_review")
    bob = as_user("bob@test.com")                       # ordinary user
    assert client.post(f"/api/admin/listings/{listing.id}/approve",
                       headers=bob).status_code == 403

def test_admin_approval_flips_status_and_stamps_published_at(client, as_user, seed):
    listing = seed.live_listing(status="pending_review")
    admin = as_user("admin@test.com", admin=True)
    assert client.post(f"/api/admin/listings/{listing.id}/approve",
                       headers=admin).status_code == 200
    data = client.get(f"/api/listings/{listing.id}").json()
    assert data["status"] == "live" and data["published_at"] is not None

def test_cannot_approve_an_already_live_listing(client, as_user, seed):
    listing = seed.live_listing(status="live")
    admin = as_user("admin@test.com", admin=True)
    assert client.post(f"/api/admin/listings/{listing.id}/approve",
                       headers=admin).status_code == 409
```

### 4.3 Schema-leak test — anonymity enforced by the response model (Milestone 4)

```python
def test_public_listing_response_never_contains_identity_fields(client, seed):
    listing = seed.live_listing(company_name="SecretCo")
    body = client.get(f"/api/listings/{listing.id}").json()
    assert "company_name" not in body and "website_url" not in body
```

Plus the frontend twin in Vitest:

```ts
// app/src/components/ListingCard.test.tsx
test("public card never leaks identity fields", () => {
  render(<ListingCard listing={{ headline: "B2B SaaS", mrr: 8000 }} />);
  expect(screen.getByText(/B2B SaaS/)).toBeInTheDocument();
  expect(screen.queryByText(/SecretCo/)).toBeNull();
});
```

### 4.4 WebSocket test — chat (Milestone 6)

```python
def test_message_reaches_the_other_participant(client, as_user, seed):
    conv, tok_buyer, tok_seller = seed.conversation_with_tokens()
    with client.websocket_connect(f"/ws/conversations/{conv.id}?token={tok_buyer}") as buyer, \
         client.websocket_connect(f"/ws/conversations/{conv.id}?token={tok_seller}") as seller:
        buyer.send_json({"text": "Is churn really 2%?"})
        assert seller.receive_json()["text"] == "Is churn really 2%?"

def test_non_participant_cannot_connect(client, as_user, seed):
    conv, *_ = seed.conversation_with_tokens()
    intruder_tok = seed.token_for("mallory@test.com")
    with pytest.raises(Exception):        # connection rejected during handshake
        with client.websocket_connect(f"/ws/conversations/{conv.id}?token={intruder_tok}"):
            pass
```

---

## 5. Per-Milestone Test Checklists

Write these from the milestone spec *before* implementing (SDD). ☐ = one test each. Endpoint paths below omit the `/api` prefix for readability — in test code it is always `/api/...` (see `design_implementation.md` §3.4).

**M0 — Hello FastAPI** *(proves the harness itself)*
- ☐ `GET /health` returns 200 `{"status":"ok"}` via TestClient.
- ☐ A row written through the sandbox endpoint is read back — proves the `session`/`client` fixtures work.

**M1 — Auth & roles**
- ☐ Register creates the user; ☐ the stored password is a bcrypt hash, not plaintext (inspect via `session`).
- ☐ Login with wrong password → 401; ☐ `GET /auth/me` without a token → 401, with a token → the right user.
- ☐ Register with an invalid role → 422 (Pydantic does this for you — test it anyway; it's a spec criterion).
- ☐ Component: router guard redirects a logged-out visitor from `/sell` to login.

**M2 — Listing builder**
- ☐ `POST /listings` creates a draft with `owner_id` = caller — even if the client sends a different `owner_id` (server must ignore it).
- ☐ Client sending `status:"live"` on create is ignored/rejected — no self-publishing.
- ☐ `PUT` on someone else's listing → 403 (or 404 — pick one in the spec and test that).
- ☐ `POST /listings/{id}/submit` flips draft → `pending_review`; ☐ submitting a non-draft → 409.
- ☐ Upload stores the file under `uploads/{listing_id}/` and records the path; ☐ uploading to someone else's listing → 403.
- ☐ Unit: form/schema validation (asking price > 0, required metrics present).

**M3 — Admin curation** *(see §4.2)*
- ☐ Approve as non-admin → 403. ☐ Approve as admin → `live` + `published_at` set.
- ☐ Reject stores the reason. ☐ Approving an already-live listing → 409.
- ☐ The seller has no endpoint path to set their own listing `live` (attempt → 403/422).

**M4 — Marketplace browse**
- ☐ `GET /listings` returns only `live` listings; ☐ drafts/pending never appear, even for their owner (owner uses their dashboard endpoint instead).
- ☐ Response contains no identity fields — the schema-leak test (§4.3).
- ☐ Filter combinations translate correctly (type + price range + min profit) — parametrized pytest case.
- ☐ Component: `ListingCard` leaks no identity fields.

**M5 — Platform NDA + access gate** *(the most important tests in the project — see §4.1)*
- ☐ `POST /auth/nda` stamps `nda_signed_at`; ☐ signing again is idempotent (timestamp unchanged).
- ☐ Buyer who hasn't signed the platform NDA cannot create an access request → 403.
- ☐ Buyer without a request → private data 403. ☐ `requested` (not yet approved) → 403.
- ☐ `approved` → 200. ☐ Owner → 200. ☐ `denied` → 403.
- ☐ `POST /listings/{id}/access-request` records the caller as buyer with initial status `requested` and a timestamp — regardless of what the client sends.
- ☐ Duplicate request for the same listing+buyer → 409 (the unique constraint).
- ☐ Only the listing's seller can approve/deny (buyer or third party → 403).
- ☐ Document download endpoint enforces the same gate (403 before approval, file after).

**M6 — Chat** *(see §4.4)*
- ☐ Non-participant WebSocket connection is rejected. ☐ Invalid/missing token is rejected.
- ☐ Message from A is received by B; ☐ message is persisted (visible via history endpoint after reconnect).
- ☐ Sender identity comes from the token, not the payload (spoofed `sender_id` in the JSON is ignored).
- ☐ History endpoint returns 403 for non-participants.

**M7 — Offers**
- ☐ `POST /offers` without approved access → 403; ☐ on a non-live listing → 409.
- ☐ Valid offer → `submitted` + an `offer_event` row exists.
- ☐ Seller accept → offer `accepted` **and** listing `under_offer` (assert both — this is the transaction test).
- ☐ Responding to an offer on someone else's listing → 403. ☐ Acting on an already-decided offer → 409.

**M8 — Notifications engine + saved searches + account lifecycle** *(security-critical — account lifecycle moved here from M1, 2026-07-17)*
- ☐ Approving a listing creates a notification for the matching saved search…
- ☐ …and none for a non-matching one. (BackgroundTasks run synchronously under TestClient — assert right after the approve call.)
- ☐ `GET /notifications` returns only the caller's notifications.
- ☐ Password reset: a valid token sets the new password; ☐ the **same token used twice → rejected** (single-use); ☐ an **expired** token → rejected; ☐ a token for user A cannot reset user B.
- ☐ `POST /auth/forgot-password` returns the **same response for a known and an unknown address** (no user enumeration — the M1 login rule, applied here).
- ☐ Email verification: the token flips `email_verified`; ☐ reusing it → rejected.

**M9 — Watchlist**
- ☐ Add → appears in `GET /watchlist`; ☐ delete → gone; ☐ the list only ever contains the caller's own items.

**M10 — Buyer verification**
- ☐ Buyer uploads own proof-of-funds file. ☐ Buyer cannot set `verified` on themselves (field ignored or 403).
- ☐ Only admin flips verification status.

**M11 — Valuation calculator**
- ☐ Unit table-test (Vitest or pytest, wherever the logic lives): (type, revenue, profit, churn) → expected range, incl. edge cases (zero profit, absurd churn).

**M12 — Deal completion** *(appended 2026-07-16 — gap review)*
- ☐ Seller marks the deal sold → listing `sold` + `sold_at` + final price recorded (derived from the accepted offer, **not** the request body), accepted offer terminal — one transaction, assert all.
- ☐ Deal fell through (re-list) → listing back to `live`, accepted offer terminal; sibling offers follow the policy the M7 spec decided.
- ☐ Both paths write `listing_event` / `offer_event` audit rows.
- ☐ Non-seller attempting either transition → 403. ☐ Either transition on a non-`under_offer` listing → 409.
- ☐ The NDA gate still guards a `sold` listing's private data (approved buyer 200, everyone else 403).

**After Phase D — the E2E golden path** (one Playwright script; run `fastapi dev` + `npm run dev` first)
- ☐ Seller signs up → creates listing → admin approves → buyer signs up → finds listing via filter → signs NDA → seller approves → buyer reads private data → chat exchange → buyer submits offer → seller accepts → listing shows "under offer" → *(once M12 lands)* seller marks it sold → listing shows "sold".
This single test touches every milestone; when it's green, your MVP demonstrably works end to end.

---

## 6. Regression Habit

Because milestones build on each other, **always run the full `npm test` before calling a milestone done** — M7's endpoint changes can silently break M5's gate. The suite stays fast (in-memory SQLite tests run in milliseconds), so there's no excuse to skip it. If you use git: commit per milestone, and only commit when `npm test` is green — that gives you a known-good checkpoint to return to.

**CI runs this same suite on every PR and on `main` pushes** (`.github/workflows/ci.yml` — backend pytest + frontend tsc/vitest), so a red PR can't merge; the local `npm test` loop stays the fast path, CI is the enforcement.

**Deferred NFR harnesses** *(recorded 2026-07-16 so they're decisions, not drift)*: **performance** — the p95 < 500 ms search NFR has no load/perf harness; build one around the Postgres swap / deploy (QA/SDET, `team_strategy.md`). ~~**Accessibility** — add an axe-core pass to the Playwright golden path when it lands at Phase D (WCAG 2.1 AA NFR).~~ **Retired 2026-07-19, shipped early (PR #32):** `app/e2e/a11y.spec.ts` runs `@axe-core/playwright` against WCAG 2 A/AA on every public and authed screen, in the `Browser (a11y + layout)` CI job — so this landed at M3 rather than waiting for Phase D, and the golden path will inherit it. **WebSocket scale** — the M6 in-memory connection manager is single-process by design; deploying beyond one process needs a pub/sub backplane (note for `devops-sre`).

---

## 7. If You Chose the Supabase Alternative (`docs/research/supabase_alternative.md` — considered and rejected; kept for comparison)

The philosophy and the per-milestone checklists above stay identical — only the tools change, because the trust boundary moves from your API into the database (RLS):

| FastAPI-stack tool | Supabase equivalent |
|---|---|
| pytest permission tests against endpoints | **pgTAP SQL tests** via `supabase test db` (files in `supabase/tests/*.sql`), or JS tests using two `supabase-js` clients signed in as different users |
| Workflow tests calling endpoints | Vitest calling `supabase.rpc("submit_offer", …)` against the local stack; assert on rows |
| Fresh in-memory DB per test | `supabase db reset` before a test run (re-applies migrations + seed); pgTAP tests run inside rolled-back transactions — auto-clean |

The NDA-gate test in pgTAP, mirroring §4.1:

```sql
-- supabase/tests/nda_gate.test.sql
begin;
select plan(2);
set local role authenticated;
set local request.jwt.claims to '{"sub":"00000000-0000-0000-0000-0000000000b0"}'; -- bob
select is_empty(
  $$ select * from listing_private where listing_id = '…l1…' $$,
  'buyer without approved access sees no private rows');
-- (seed an approved access_request for bob in seed.sql, then:)
select isnt_empty(
  $$ select * from listing_private where listing_id = '…l2…' $$,
  'buyer with approved access sees private rows');
select * from finish();
rollback;
```

Vitest component tests and the Playwright E2E script are identical in both stacks.

---

## 8. TL;DR Quick Reference

```bash
# once
pip install pytest                          # backend/ venv
npm i -D vitest @testing-library/react ...  # app/ ; Playwright later

# every day
npm test                     # pytest (API + permissions) + vitest, one command
cd backend && pytest -q      # fast loop while building endpoints
cd backend && pytest -q -x --lf             # only last failures

# per milestone (SDD loop)
spec → write its tests (fail) → implement → tests pass → full `npm test` green → commit → next
```
