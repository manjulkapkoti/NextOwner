# Plan 013 — E2E Golden Path (Phase D)

> Implementation plan for [`spec.md`](./spec.md). Read that first — in particular D1 (one test, fourteen steps) and D2 (a real backend), which decide the shape of everything below.

---

## Schema deltas

**None.** No new table, no new column, no migration. The golden path writes only rows the product's own endpoints create, through those endpoints, as a user would.

## Endpoints

**None.** No route is added, changed, or removed — including for D11's fix, which is a missing *caller* of `POST /api/listings/{id}/submit`, not a missing capability. The path exercises routes that shipped in M1–M12 and asserts nothing about their shape that their own suites do not already assert.

The one new *executable* is not an endpoint: `seed/make_admin.py`, a CLI. See § Permission gates.

## Permission gates

**No new `permissions.py` function** — the fifth milestone with none, after M3, M4, M11 and M12. There is no new trust boundary because there is no new caller: every request in the run arrives from a browser holding a token issued by `POST /api/auth/login`, and hits gates that already exist.

The privilege-adjacent artefact is `seed/make_admin.py`, which sits **outside** the API entirely:

| | |
|---|---|
| **Grants** | `user.is_admin = 1` on one existing row |
| **Reachable from** | a shell with filesystem + database access |
| **Reachable from a browser** | never — no route, no handler, no import from `app.main` |
| **Refuses** | a user that does not exist (H2) · a non-SQLite `DATABASE_URL` (H3) · a missing `NEXTOWNER_ALLOW_ADMIN_PROMOTION=1` (H4) |
| **Precedent** | `backend/tests/conftest.py::admin_headers` does the same `UPDATE` for the same reason, and says so |

## Frontend

**Two components change** (D11, D12) — the gaps the path found. Everything else the path walks already exists and already has Vitest coverage: `RegisterForm`, `AdminQueue`, `BrowseListings`, `ListingCard`, `ListingDetail`, `NdaModal`, `RequestAccessPanel`, `GatedPanel`, `PrivateSection`, `AccessRequestQueue`, `ConversationList`, `ChatWindow`, `OfferThread`, `MyOffers`, `ListingOffersQueue`, `DealActions`.

| Component | Change | Criteria |
|---|---|---|
| `MyListings.tsx` | A **Submit for review** action on `draft` rows only, posting to the existing `POST /api/listings/{id}/submit`, then refreshing the row. Needs a busy state (no double-submit) and an inline error, matching the file's existing `Alert` idiom. | F1, F2 |
| `ListingWizard.tsx` | A **Business type** select on the Basics step, bound to the `type` key already in `EMPTY`; Metrics step guidance corrected and its five required fields marked required. | F3, F4 |
| `ListingWizard.tsx` *(added mid-build)* | A **Detailed financials** field on the private step, bound to the `detailed_financials` key already in `EMPTY`; **Description** moved to the Basics step. | F5, F6 |

*F5/F6 were added after the golden path first ran — see § What the run actually found.*

Neither touches `lib/api.ts`, a store, or a route. `MyListings` is currently deliberately router-free (its header comment says so) and stays that way — the action calls the API and re-fetches, it does not navigate.

*Business-type values must match what the backend already stores*, so they come from the existing vocabulary (`saas`, `ecommerce`, `content`, `marketplace`, `agency`, `other` — confirm against `seed/seed.py`'s templates and M4's filter before writing the option list, rather than inventing a set).

Two **config** changes, neither of which touches a component:

- `app/vite.config.ts` — add a `preview.proxy` block mirroring the existing `server.proxy` (D4). Without it the built bundle has no path to the API, because `vite preview` does not read `server.proxy`.
- `app/playwright.golden.config.ts` — **new** (D3). Its own `webServer` array (backend, then frontend), `reuseExistingServer: false`, `retries: 0`, `testMatch` scoped to the two golden files so the UI suites can never be pulled into it.

*If a selector turns out to be unreachable — no accessible name, no stable role — the fix is to add the accessible name to the component, not a brittle CSS selector to the test. That is a real possibility on `DealActions` and `OfferThread`, which no Playwright suite has ever driven. Such a change is in scope and is a product improvement; a `nth-child` chain is not.*

## Response models

**None.** No response model is added or altered. T1/T2 assert the *rendered page* omits what the public and gated models already omit by schema — a second, independent observation of the same property, one layer further out.

## Errors

**No new `AppError` subclass and no new machine `code`.** The milestone raises none; it *observes* the ones M1–M12 raise.

`make_admin` is a CLI and so does not use the HTTP error contract at all. It exits non-zero with a plain-English message on stderr for each of its three refusals (H2/H3/H4). It prints the email it promoted on success, so a CI log records what was granted.

Frontend error states touched: none new. X1 asserts an **existing** one — that a failed `/api/auth/*` call surfaces an error and does not produce an authenticated session.

## Analytics events

**None.** There is still no `track()` wrapper in the codebase (recorded as a standing gap since M4), and a test run must not emit product analytics in any case.

## Data protection

**No new PII field and no new person-referencing table.** The run creates two ordinary user rows (a seller and a buyer) in a throwaway database that is deleted at the start of the next run (D7).

One thing worth stating because it is easy to get wrong later: **the golden path's fixture emails must stay obviously synthetic** — `seller@e2e.example.com`, `buyer@e2e.example.com`, `admin@e2e.example.com`. A real-looking address in a committed test is the kind of thing that eventually gets mailed by a milestone that adds a send.

> **Corrected during the build.** This originally prescribed the reserved `.test` TLD (RFC 2606), and that is unusable here: `EmailStr` (email-validator) rejects special-use TLDs outright — *"the part after the @-sign is a special-use or reserved name that cannot be used with email"* — so `seller@e2e.test` is an address **no human could register either**. The IANA-reserved `example.com` satisfies the same intent (unmailable, obviously fictional) and matches what `seed/seed.py` already uses. The harness moved rather than the validator, which is behaving correctly.

---

## Build order

Eight slices. The harness comes before the path because a path with nowhere to run cannot be written; the product gaps come before the path because G3 cannot click a button that does not exist; the guards come last because they assert properties of the finished suite. **No checkboxes — the red test list is the status** (constitution Article 3 §1).

**1 — The hermetic harness.** `app/playwright.golden.config.ts` + the `vite.config.ts` `preview.proxy` block + the `e2e.db` lifecycle (delete, then start uvicorn bound to it via `DATABASE_URL`). *Turns green:* **H1**. *Why first:* every remaining slice needs a browser that can reach a real backend; until this exists there is no way to run anything else, and no way to tell a broken assertion from a broken harness.

**2 — `seed/make_admin.py`.** The CLI plus its three refusals. *Turns green:* **H2, H3, H4**. *Why second and not later:* G4 needs an admin, so slice 3 cannot finish without it — and writing it as its own slice keeps the one privilege-granting artefact in a commit a reviewer can read on its own, rather than buried in a 400-line test script.

**3 — The product gaps (D11, D12).** The Submit-for-review action on `MyListings` draft rows, the wizard's business-type select, and the corrected Metrics guidance — with their Vitest tests. *Turns green:* **F1, F2, F3, F4** — and, once the path ran and found them, **F5 and F6** in a follow-on commit against the same component. *Why here:* G3 clicks the button this slice creates and G2 selects the type this slice adds, so leg 1 cannot finish without it. It sits **after** the harness rather than first because it is the only slice whose tests are ordinary Vitest component tests — they need no browser, no backend and no database, so they are the one thing in this milestone that could have been built in any order, and putting them where their consumer needs them keeps the dependency chain readable. This is also the slice an appsec reviewer will care about; keeping it as one commit that touches two components and no backend is what makes that review cheap.

**4 — Golden path, leg 1: listed and live.** `golden-path.spec.ts` skeleton (two contexts, the shared unique headline) and steps G1–G4. *Turns green:* **G1, G2, G3, G4**. *Why here:* this leg is entirely seller-plus-admin, so it depends on slice 2 and on nothing later. It is also the leg most likely to surface harness problems (first real login, first real form submission), which is a reason to hit it early rather than at step nine.

**5 — Golden path, leg 2: through the gate.** G5–G10 — buyer registers in the second context, finds the listing, signs the NDA, requests access, the seller approves, the buyer reads the private section. *Turns green:* **G5, G6, G7, G8, G9, G10**. *Why here:* it needs a `live` listing, which is exactly what slice 3 leaves behind. This is the trust core walked in a browser and is the leg whose failure would matter most.

**6 — Golden path, leg 3: to sold.** G11–G14 — chat delivery, offer, accept, mark-sold. *Turns green:* **G11, G12, G13, G14**. *Why last of the three legs:* every step needs approved access, which slice 4 establishes. G11 (WebSocket, two live contexts) is the highest-risk step in the milestone and is deliberately not also the first — by the time it runs, the harness is proven, so an intermittent failure here is evidence about the product rather than about the setup (see § Errors & failure modes).

**7 — The trust checks.** T1–T3 as three separate tests. *Turns green:* **T1, T2, T3**. *Why after the path:* T1 and T2 need a `live` listing with private data behind the gate, and the cheapest correct way to arrange that is the helper the path already grew across slices 4–5. Writing them earlier would mean building that arrangement twice.

**8 — Enforcement and the anti-vacuity guards.** The CI job, `golden-path.guards.spec.ts` (X1), and the source scan (X2). *Turns green:* **H5, X1, X2**. *Why last:* X2 scans the finished golden spec, and H5 pins a workflow job that should not be wired up until the suite it runs is green. Wiring CI first would put a red required check on the branch for six slices and train everyone to ignore it.

**Nothing in this milestone deletes a test.** No throwaway surface is being retired, so the red count only falls.

> **How slices 4–7 actually went, since it differs from the shape above.** The Build order assumed `golden-path.spec.ts` would be *written* leg by leg; the red-set commit had already written all fourteen steps and the three trust checks in full. So slices 4–7 were not authoring but **running** — each leg failed, was diagnosed against the real product, and either the product or the assumption was corrected. That is the same work in a different order, and it is worth recording because it changed what the slices cost: leg 1 was the expensive one (four separate corrections before G1–G4 held), and the trust checks T1–T3 passed on their first execution with no changes at all.

---

## The red set as actually measured (2026-07-30, before any implementation)

Not predicted — run. `python scripts/check_spec_coverage.py 013` reported **28/28 criteria cited** at this point. The spec grew to **30** mid-build (F5, F6 — see § What the run actually found), and the checker reports 30/30 now.

| Suite | Result |
|---|---|
| `backend/tests/test_e2e_harness.py` | **6 failed** — H1, H2, H3, H4, H5 + the files-readable guard |
| `src/components/MyListingsSubmit.test.tsx` | **1 failed** (F1), **1 passed** (F2) |
| `src/components/ListingWizardBasics.test.tsx` | **2 failed** (F3, F4) |
| `e2e/golden-path.guards.spec.ts` | **2 passed** (X1, X2) |
| `e2e/golden-path.spec.ts` | not runnable — `playwright.golden.config.ts` does not exist yet (slice 1) |

**Three tests pass before implementation, and Article 3 §2 requires each to be shown a pin rather than vacuous. Two are; one is not:**

- **X2 — a legitimate pin.** `golden-path.spec.ts` exists and genuinely contains no `page.route`/`fulfill`/token injection. The test asserts a real property of a real file and will fail the moment someone copies the stubbing idiom from `screens.spec.ts`. This is the M5 E4/E5 case exactly.
- **X1 — a legitimate pin.** It passes because the product already fails closed: a 500 from `/api/auth/**` leaves `RegisterForm` showing an `Alert` and no session. That behaviour is what X1 exists to protect, and it is really being exercised (the 500 comes from the stub, and the assertion reads the rendered alert). Verify by sabotage anyway when slice 8 lands — make the form navigate on error and confirm X1 goes red.
- **F2 — vacuous today, and must be re-verified.** It passes only because **no submit action exists anywhere**, so "absent on non-draft rows" is trivially true. It becomes a real pin the instant F1's button ships. **Do not treat F2 as green until after slice 3**, and confirm it then by rendering a `draft` row (the action must appear) alongside the non-draft rows (it must not) — if F2 still passes when the button is wired to *every* row, it is testing nothing.

**One consequence of adding these files that slice 1 must handle:** `app/playwright.config.ts` has `testDir: './e2e'` and no `testMatch`, so a bare `npx playwright test` / `npm run e2e` now picks up `golden-path.spec.ts` and runs it against a backend-less `vite preview`, where it cannot pass. The default config must exclude the two golden files, and the golden config must claim them. CI is unaffected — its browser job names `e2e/a11y.spec.ts e2e/layout.spec.ts` explicitly.

---

## What the run actually found (2026-08-03, after implementation)

The path was written blind against a product nobody had driven from a browser. Running it corrected nine things. **Three were real defects, two were recorded deviations, and four were wrong assumptions in the test** — and the split is worth keeping, because a milestone that quietly "fixed the tests" nine times would have learned nothing.

**Real defects in shipped code (all fixed here):**

1. **`detailed_financials` was collected nowhere** (F5). Carried in the wizard's `EMPTY`, rendered by no input — the same defect as `type`, on the field that *is* the data room. Before this, no listing created through the UI could have anything behind the NDA gate at all.
2. **The wizard's privacy promise was false** (F6). The step headed *"never shown publicly"* collected `description`, which is on `ListingPublic`. Found because the path took the wizard at its word and put its secret there — and then G8 saw it on the anonymous card.
3. **X1 was itself vacuous.** Its "no session was created" assertion read a *log-out button*, and no such button exists on any page in the product — logout lives inside the account menu. A guard against vacuity that could never have failed. Now reads the account menu, and sabotage-verified.

**Recorded deviations (deliberate, not discovered):**

4. **The e2e backend runs with raised auth rate limits** (`LOGIN_RATE_LIMIT_MAX`/`REGISTER_RATE_LIMIT_MAX` = 200, set in the golden config's `webServer.env` and nowhere else). The limiter is per IP and every session in the suite is localhost; the path performs ~8 logins against a production default of 5/minute, so the suite would fail on a control it does not test and `pre-011` already covers. **Raised, not disabled** — the limiter is still wired in, so a change that removed it entirely is still observable.
5. **Fixture emails moved off `.test`** — see § Data protection above.

**Wrong assumptions in the test (product was right):**

6. **"No public result" was asserted as "the headline is absent from the page."** Browse echoes the search term back as an active-filter chip, and Playwright matches text by substring, so that assertion fails against a *working* marketplace. Now scoped to result cards.
7. **The access-request queue was located by the buyer's email**, which `BuyerProfile` carries nowhere by construction (spec 005 G3/S3). Rewritten to assert the email is **absent** — the check it should always have been.
8. **The sold chip was matched by substring**, which also matches "Sold for $445,000" and fails strict mode on a correct product.
9. **A navigation race, worked around rather than papered over.** `BrowseListings` debounces the search box 250ms and then writes `q` to the URL; clicking a result inside that window navigates to the detail page and the debounce *then* fires from an unmounted component, throwing the browser back to the marketplace. The path now waits for the search to land before clicking, and asserts the detail view rendered rather than only that the address bar changed. **This is a real race in the product**, not a test artefact — it is recorded rather than fixed because it needs a `BrowseListings` change (cancel the timer on unmount) that no criterion in this spec covers.

**And one finding about the enforcement rather than the product:** `check_spec_coverage.py` reports **30/30** for this spec — and still reports 30/30 with the F5, G11 and T2 *tests* renamed out of existence, because in each case a **comment** elsewhere in the tagged file names the id. This is the spot-check the § Verification notes below prescribed, and it found exactly what it predicted. The gate proves *citation, not verification*, and prose satisfies it as readily as a test. Left as-is deliberately: tightening it is a change to a shared script that gates all thirteen specs, and doing that late in an unrelated milestone is how a green CI turns red for reasons nobody scheduled. **Carried as a follow-up.**

---

## Verification notes (things to actually run, not assert in prose)

Recorded here because three of the last four milestones produced a Build order that was wrong about which slice turned which test green, and the correction each time came from a real run rather than a re-guess:

- After each slice, re-run `npx playwright test --config=playwright.golden.config.ts` and record the **observed** red-count delta. If it disagrees with the slice list above, the list is wrong — amend it here rather than reasoning about why the run is mistaken.
- **X1 and X2 must be seen failing before they are believed** (Article 3 §2 — a sabotage test nobody has seen fail proves nothing). For X2, temporarily add a `page.route` to the golden spec and confirm the scan goes red. For X1, confirm it goes red if the app is changed to enter an authenticated state without a successful response.
- **H1 needs its own sabotage:** point `DATABASE_URL` at `nextowner.db`, confirm the check fails, and put it back. A hermetic-run assertion that has never seen a non-hermetic run is a claim, not a test.
- Run `python scripts/check_spec_coverage.py 013` and **check the criterion count, not the exit code** — it must report **30** (F1–F6, G1–G14, T1–T3, H1–H5, X1–X2). M12's spec reported `10/10` for a spec with 47 criteria, and CI would have gone green on 21% of it. *Done: 30/30.*
- **Watch for false-positive citation in the files tagged `013`.** The checker matches a criterion id anywhere in a tagged file, bounded by non-alphanumerics — so a literal `<h1>` in a frontend test would silently satisfy **H1**, and `X2`-shaped strings are easy to write by accident. Prefer role-based queries over raw tag names in these files, and when the count first reaches 28/28, spot-check two or three ids by deleting the citing test and confirming the checker goes red.
