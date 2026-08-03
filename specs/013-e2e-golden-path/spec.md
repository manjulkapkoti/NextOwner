# Spec 013 — E2E Golden Path (Phase D)

> **Milestone:** the Playwright golden path — `docs/design_implementation.md` Part 4 (the *E2E golden path* bullet), `docs/milestones.md` § Progress tracker (the **E2E** row), `docs/testing_guide.md` §5 (*After Phase D*), `docs/security.md` §7 (final bullet).
>
> **What is different about this milestone.** Every milestone from M1 to M12 added product surface and then tested it. This one is mostly the inverse: it adds a *test* and the harness that lets a test drive the real stack, which changes the review question from *"is this new door gated?"* to **"can this test pass while the product is broken?"** Most of the criteria below exist to answer that second question, because a golden path that can go green vacuously is worse than no golden path — it is a green light wired to nothing.
>
> **It does not stay purely test-only, and the reason is the milestone's first real finding.** Writing these criteria surfaced that **`POST /api/listings/{id}/submit` has no caller anywhere in the frontend** — a seller can create a draft and then has no way to get it reviewed, so the M2→M3 handoff has a backend, a full set of backend tests, and no browser path at all. The golden path cannot walk around that; it *is* step G3. Two smaller defects came with it (the wizard never collects `type`; the metrics step instructs sellers to leave required fields blank). All three are fixed here under the F group, with criteria, per the M10 rule that new surface gets criteria rather than a pass. **Consequence to accept knowingly:** this milestone now touches a state transition and a form, so `scripts/check_appsec_trigger.py` will require an independent appsec pass that a purely test-only milestone would not have needed.

---

## FR references

The golden path does not implement a requirement; it demonstrates that the ones already built compose. It walks, in order: **FR-1** (register/login), **FR-5** (seller creates a listing), **FR-7** (pending-review → admin approves), **FR-6** (anonymous public listing, identity hidden), **FR-10** (browse + keyword search), **FR-13/FR-14** (platform NDA + seller-approved per-listing access), **FR-15** (approved buyer sees full financials and identity), **FR-16** (realtime messages), **FR-17** (offers/LOI, seller accepts), **FR-8** (state changes propagate — `under_offer`, then `sold`).

---

## User stories

- **As the product owner,** I want one script that walks a business from listed to sold in a real browser, so that "the MVP works" is something I can watch rather than something I am told.
- **As a developer,** I want that script to run in CI on every PR, so that a change which breaks the trust chain between two milestones fails before it lands, not after.
- **As the person responsible for security,** I want the same run to prove the browser never renders what the API withheld, so that the golden path is a regression check and not just a demo.

---

## Decisions

- **D1 — The golden path is ONE test with named steps, not fourteen tests.** The constitution (Article 3 §2) says every criterion becomes exactly one test, and that rule needs an honest reading here rather than a literal one. Fourteen isolated tests would each re-arrange the world and assert one endpoint — which is what `backend/tests/` already does, ~850 times, better and faster. The *only* thing this milestone can prove that those cannot is that **state carries forward across all fourteen**, and a test that re-seeds between steps has thrown exactly that away. So G1–G14 are `test.step()` calls inside one `test()`, each step titled with its criterion id. `check_spec_coverage.py` is satisfied (it looks for the id anywhere in the file), the Playwright report names the failing step, and a failure at G4 correctly prevents G5–G14 from claiming anything. **The three T-criteria are genuinely separate tests** — they have independent arrangements and no shared narrative.
- **D2 — The golden run drives a REAL backend against a REAL database.** This is the whole point and it is worth stating as a decision, because the three Playwright suites already in `app/e2e/` do the opposite: `screens`, `a11y` and `layout` stub every API call with `page.route()` and drive `vite preview` with no backend at all. That was correct for them (they check pixels and axe rules, and a backend would be a flake source for no gain) and it is *disqualifying* here. A golden path whose API responses are fixtures proves that the frontend can render fixtures. See X2, which is the guard that keeps this true after the first person copies a neighbouring file.
- **D3 — A separate Playwright config, not a second project inside the existing one.** `app/playwright.config.ts` starts `vite build && vite preview` and nothing else; adding the backend to its `webServer` array would make `npm run e2e:a11y` — the tight UI loop — depend on a Python environment and a database. So the golden path gets `app/playwright.golden.config.ts` with its own two-server `webServer` array. Cost: one more config file. Benefit: the existing UI loop is untouched, and the two suites cannot flake into each other.
- **D4 — `vite preview` needs its own proxy entry.** `vite.config.ts` proxies `/api` and `/ws` under the `server` key, which `vite dev` reads and `vite preview` does not. The golden path drives the **built** bundle (same reason the existing config gives: the built bundle is what ships), so a matching `preview.proxy` block is required or every request 404s against the static server. This is additive and invisible to the dev server and to Vitest.
- **D5 — Admin is granted by a CLI, never by an endpoint.** There is deliberately no HTTP path that grants admin (M1 decision, unchanged at M3 — `backend/tests/conftest.py` promotes with a direct `UPDATE` and says so). The E2E has the same need and must not solve it differently: `security.md` §6 names *"test-only backdoors in prod"* as an explicit threat, and an env-flag-gated bootstrap route is one — a flag misread in one environment grants admin over HTTP forever. `seed/make_admin.py` is a CLI: it needs filesystem and database access, adds **zero route surface**, and is called from Playwright's global setup.
- **D6 — `make_admin` promotes an existing user and never creates one.** This is the guard that matters, and it is stronger than gating on the database filename. A tool that can only flip `is_admin` on a row that already exists cannot inject an account; the operator must first register through the real endpoint, which is rate-limited, validated, and logged. It also refuses any non-SQLite URL (the same guard `seed/seed.py` carries, for the same reason: a Postgres URL means something closer to production, and that path deserves a deliberate decision rather than this script). **Deviation from the option as presented at scoping time, recorded rather than absorbed:** the previewed sketch refused unless `DATABASE_URL` pointed at the e2e database. I implemented an explicit `NEXTOWNER_ALLOW_ADMIN_PROMOTION=1` opt-in instead, because "promote the first admin" is a real operational need that a hardcoded e2e-only lock would make this script useless for — pushing the next person to write a second, less careful tool. The env opt-in delivers the same property (it cannot run by accident) without pretending the need is fictional. **Owner-overridable** — say the word and it becomes a filename check.
- **D7 — A dedicated, deleted-first database; no seed data.** The run writes to `e2e.db` via `DATABASE_URL`, deleted before the backend starts, so the run is hermetic and never touches the developer's `nextowner.db`. It also does **not** load `seed/seed.py`: those ~30 listings would sit in the marketplace that G6 searches, turning "the buyer finds the listing" from an assertion into a coincidence, and the seeded buyer already has a signed NDA and approved access — the exact states G7–G9 exist to establish.
- **D8 — Two browser contexts, not two sequential logins.** The seller and the buyer are separate `browser.newContext()` sessions alive at the same time. G11 (chat) requires it — delivery to *the other participant* is unobservable if the other participant is a logged-out tab. It also makes the rest of the path honest: a single context that logs out and in between steps is testing localStorage, not two humans.
- **D9 — No pixel assertions, and no new ones introduced.** `ci.yml` already records why (`Windows dev / Linux CI`, antialiasing, no Docker). The golden path asserts text, roles and URLs only.
- **D10 — The path uses a unique headline as its search term.** G6 searches for the exact headline G2 created. With D7's empty database this is deterministic, and it keeps G6 asserting *"the buyer can find this listing"* rather than *"a listing exists"*.
- **D11 — The missing submit action is fixed, not routed around.** Three options were weighed. Driving G3 with a direct `request.post()` from the test was rejected: it would make G3 the one step in the path that proves nothing about the product, and it would leave a shipped, user-facing gap invisible precisely because the test that found it had worked around it. Cutting G1–G3 was rejected because it would delete the milestone's central claim ("this single test touches every milestone"). So the button ships: a **Submit for review** action on `draft` rows in `MyListings`, calling an endpoint that already exists, is already gated by `get_owned_listing`, and already 409s an illegal transition. **No backend change** — this is a missing caller, not a missing capability. The general shape is one this repo has hit before: the corridor between two milestones had no owner, so M2 built the door and M3 built the room and nobody built the hallway.
- **D12 — The two wizard defects are fixed here too, and one of them was a choice between a UI fix and a schema change.** *(a)* `ListingWizard` carries `type` in its form state but renders no input for it, so every listing created through the UI stores `type: ''` — and M4's browse filter is `if query.type`, so those listings can never match a type filter. A `Business type` selector is added to the Basics step. *(b)* The Metrics step's guidance says *"Leave anything you do not have blank"*, while `ListingCreate` requires `ttm_revenue`, `ttm_profit`, `mrr`, `churn_pct` and `customers` — a blank field serializes to `""`, which fails Decimal validation, so following the wizard's own instruction produces a 422. **Fixed on the UI side, not by relaxing the schema:** making five money/metric columns nullable would ripple into M4's filters, M11's valuation inputs and every response model that reads them, to fix a sentence. The fields are marked required and the guidance now says to enter `0` where a metric does not apply — which is also the more accurate datum, since "this business has no MRR" is a fact worth storing as zero rather than as absent.

---

## Acceptance criteria

### F — the product gaps this milestone found and fixes (D11, D12)

- **F1** — GIVEN a seller viewing a `draft` listing on `/my-listings`, WHEN they use the submit-for-review action, THEN the row's status becomes `In review` and the action is no longer offered on that row.
- **F2** — GIVEN a seller whose listings include one `live`, one `pending_review` and one `sold` row, WHEN `/my-listings` renders, THEN the submit-for-review action appears on none of them.
- **F3** — GIVEN the wizard's Basics step, WHEN the seller selects a business type and completes the wizard, THEN the created listing carries that type rather than an empty string.
- **F4** — GIVEN the wizard's Metrics step, WHEN it renders, THEN every field `ListingCreate` requires is marked as required and the step's guidance nowhere instructs the seller to leave a required field blank.
- **F5** — GIVEN the wizard's private step, WHEN the seller enters detailed financials and completes the wizard, THEN the created listing carries them, rather than the field being held in form state and collected nowhere.
- **F6** — GIVEN the wizard step whose guidance promises the seller that its contents are never shown publicly, WHEN it renders, THEN it contains no field that `ListingPublic` exposes.

> **F5 and F6 were added mid-build, after the golden path ran.** They are two more instances of the D12(a) defect — a field carried in `EMPTY` that no input ever collects — found the only way they could be: by driving the real wizard and then reading the real listing it produced. Recorded as criteria rather than folded in silently, per the M10 rule that new surface gets criteria, not a pass.
>
> **F5** is the same bug as `type` on a more consequential field: `detailed_financials` is the data room's entire contents, so before this fix no listing created through the UI could have anything behind the NDA gate at all — M5 built the gate, M2 built the wizard, and nothing connected the seller to the room. It is invisible to every backend test, because the API accepts the field perfectly well; only a caller was missing.
>
> **F6** is the more serious of the two, because it is a false statement rather than an absent one. The step headed *"Only shared with buyers you approve — never shown publicly"* collected `description`, which is on `ListingPublic` and renders on the anonymous card. A seller who believed the sentence would put confidential detail in a public field — and the golden path did exactly that, which is how it was found. The fix moves the public copy to the public step rather than softening the sentence: the promise is the product's, and it should stay absolute.

### G — the golden path (one test, fourteen steps; D1)

- **G1** — GIVEN an empty database and an anonymous visitor, WHEN the seller registers through `/register` and lands in the app, THEN the nav shows an authenticated session and `/my-listings` is reachable without a redirect to `/login`.
- **G2** — GIVEN the signed-in seller, WHEN they complete the listing wizard at `/sell` with a unique headline and full financials, THEN the listing appears on `/my-listings` with status `draft`.
- **G3** — GIVEN that draft, WHEN the seller submits it for review, THEN its status on `/my-listings` becomes `pending_review` and no public browse result exists for its headline.
- **G4** — GIVEN a listing in `pending_review` and an admin session, WHEN the admin approves it from `/admin`, THEN the listing's status becomes `live` and it disappears from the admin queue.
- **G5** — GIVEN the live listing and a second browser context, WHEN a buyer registers through `/register`, THEN the buyer holds an independent authenticated session while the seller's session remains signed in.
- **G6** — GIVEN the signed-in buyer on `/browse`, WHEN they search for the seller's exact headline, THEN the listing appears in the results and its card shows no company name, domain or seller identity.
- **G7** — GIVEN the buyer on the listing detail page with no signed NDA, WHEN they choose to request access, THEN the platform NDA modal opens and its signing action stays disabled until the confirmation box is ticked.
- **G8** — GIVEN the NDA modal open, WHEN the buyer ticks the box and signs, THEN the panel reports the access request as pending and the private financials are still not on the page.

> **G7/G8 were rewritten after reading `RequestAccessPanel`.** The first draft assumed signing and requesting were two screens; they are one flow — the *Request access* button opens the NDA modal for a buyer who has not signed, and the modal's single *Sign and request access* action does both (`RequestAccessPanel.tsx:100`, `NdaModal.tsx:108`). Splitting the criteria along the UI's real seam is better than the original split anyway: G7 now pins the **click-wrap rule** that `NdaModal`'s own comment calls load-bearing — *"a signature that could be given without the affirmative act is not a signature"* — which no criterion covered before.
- **G9** — GIVEN a pending access request, WHEN the seller approves it from `/my-listings/:id/requests`, THEN the request shows as approved in the seller's queue.
- **G10** — GIVEN approved access, WHEN the buyer reloads the listing detail page, THEN the private section renders the company name and the financials the public card withheld.
- **G11** — GIVEN buyer and seller both signed in, WHEN the buyer sends a chat message from `/messages/:id`, THEN the seller's open conversation receives that exact text without a reload.
- **G12** — GIVEN the buyer with approved access, WHEN they submit a structured offer from the listing detail page, THEN the offer appears in the buyer's `/my-offers` with status `submitted`.
- **G13** — GIVEN a submitted offer, WHEN the seller accepts it from `/my-listings/:id/offers`, THEN the offer shows `accepted` and the listing's status becomes `under_offer`.
- **G14** — GIVEN a listing under offer, WHEN the seller marks the deal sold, THEN the listing's status becomes `sold`, the recorded final price equals the accepted offer's price, and the listing no longer appears in public browse.

### T — trust checks in the real browser (separate tests; D1)

- **T1** — GIVEN the live listing from the golden path and an anonymous visitor, WHEN they open its detail page, THEN the page renders the public summary and nowhere contains the company name, the domain, or the seller's email.
- **T2** — GIVEN a second buyer who is authenticated but has no approved access, WHEN they open the same listing's detail page, THEN they see the locked gate and the page nowhere contains the private financials.
- **T3** — GIVEN an authenticated non-admin buyer, WHEN they navigate directly to `/admin`, THEN the curation queue does not render and no pending listing's headline appears on the page.

### H — the harness (what makes the run repeatable and enforced)

- **H1** — GIVEN a developer with a populated `nextowner.db`, WHEN the golden config's servers start, THEN the backend is bound to a dedicated `e2e.db` that was deleted first, and `nextowner.db` is byte-identical after the run.
- **H2** — GIVEN an email address that no user row matches, WHEN `make_admin` is run for it, THEN it exits non-zero, reports that the user must register first, and creates nothing.
- **H3** — GIVEN a `DATABASE_URL` that is not SQLite, WHEN `make_admin` is run, THEN it refuses before opening a connection and exits non-zero.
- **H4** — GIVEN `NEXTOWNER_ALLOW_ADMIN_PROMOTION` unset, WHEN `make_admin` is run against a valid SQLite database and an existing user, THEN it refuses and exits non-zero.
- **H5** — GIVEN `.github/workflows/ci.yml`, WHEN the workflow is parsed, THEN a job runs the golden-path config and it carries neither `continue-on-error` nor a conditional that skips it on pull requests.

### X — the run cannot pass vacuously (the sabotage criteria)

- **X1** — GIVEN a backend forced to return 500 for every `/api/auth/*` call, WHEN the seller submits the registration form, THEN the app surfaces an error and never reaches an authenticated `/my-listings`, proving G1's assertion reads a real response rather than a state the app enters unconditionally.
- **X2** — GIVEN `golden-path.spec.ts`, WHEN its source is scanned for request interception, THEN it contains no `page.route`, no `fulfill` and no pre-injected auth token, so every response in the golden run came from the real backend.

> **X1 lives in a sibling file, `golden-path.guards.spec.ts`, not in the golden spec** — it must stub a failure to do its job, and X2 forbids exactly that idiom inside `golden-path.spec.ts`. Keeping them in one file would make the two criteria contradict each other; keeping them apart is what lets X2 be a mechanical scan with no exceptions to encode.

---

## Security & abuse

This milestone adds no route and **no new `permissions.py` function** — the fifth such milestone, after M3, M4, M11 and M12. It does now add a *caller* of a state transition (D11), which is why the appsec trigger fires even though no boundary moved. Its security content is of three kinds:

**0. The new caller, which changes nothing about who may do what.** The Submit-for-review button posts to `POST /api/listings/{id}/submit`, a route that shipped in M2 with `get_owned_listing` in front of it and a `draft`-only transition guard behind it. The button is **UX, not a boundary** — `security.md` §3's standing rule, that route guards and hidden buttons are never the gate. Two consequences worth writing down rather than assuming: hiding the action on non-`draft` rows (F2) is a nicety and the server's 409 is the actual control, and a seller who forges a request for someone else's listing still gets the 404 `get_owned_listing` has returned since M2. **No negative test is added at the API layer because none is missing** — `backend/tests/test_listing_lifecycle.py` already covers wrong-owner and wrong-status on this exact route. Adding a duplicate here would create a second home for a claim, which Article 4 warns against.

**1. The new artefact that is not a route.** `seed/make_admin.py` grants the highest privilege in the product. It is covered by H2/H3/H4 above, and the three properties are deliberate: it **cannot create** a principal (only promote one that registered through the real, rate-limited endpoint), it **cannot touch a non-SQLite database**, and it **cannot run without an explicit environment opt-in**. Note what is *not* claimed: this is not a defence against someone who already has shell access and the database file — nothing at that layer can be. It defends against the two realistic failures, which are a script run in the wrong directory and a CI job pointed at the wrong environment.

**2. The browser half of gates the API already enforces.** `security.md` §7's final bullet calls a passing golden path *"a security regression check"*. That is only true for what it actually asserts, so T1–T3 assert the three things the backend suite structurally cannot: the backend tests prove the API **withholds** private data, and T1–T3 prove the **browser does not render it anyway** — from a stale store, an optimistic cache, or a component that reads a field the response model no longer sends. That gap is not hypothetical in this codebase: the M11 review found a nav link invisible on the exact viewport its own comment named as its audience, because jsdom cannot evaluate a media query, and the standing carryover about `accessStore.privateData` surviving a 403 describes a stale-frame misattribution that only a real browser can observe.

**What this milestone deliberately does not do:** it does not re-test the gates themselves. `test_nda_gate.py` remains the crown jewels; three browser checks are a smoke test over them, not a replacement, and anyone reading T1–T3 as coverage of the NDA gate has misread them.

---

## Errors & failure modes

- **The vacuous-pass failure is the one that matters, and it has two criteria (X1, X2)** rather than a note. Every other milestone's tests fail when the product breaks; this one could keep passing — against stubs, against a stale server, against a database left over from the previous run. X1 sabotage-verifies the whole chain (break the backend, the suite must go red at G1); X2 pins the specific way it would rot, which is someone copying the stubbing idiom from `screens.spec.ts` two directories away.
- **Flake is a correctness failure here, not an annoyance.** A golden path that fails one run in five gets marked non-blocking within a month, and then it is decoration (`ci.yml` already records this reasoning for the npm-audit gate). Mitigations are structural, not retries: an empty database per run (D7), a unique headline (D10), Playwright's auto-waiting assertions rather than fixed sleeps, and **no pixel comparison** (D9). The golden config sets `retries: 0` locally — a step that needs a retry to pass is reporting a real race in the product, and hiding it is the opposite of what this suite is for.
- **`reuseExistingServer` is `false` for the golden config**, unlike the UI config. Reusing a running backend would mean reusing its database, and D7's hermetic run is the property that makes the whole path deterministic.
- **WebSocket delivery (G11) is the most likely genuine flake** and the most likely genuine bug — M6's carryover documents a multi-minute hang in this exact area that read as environment flakiness and was a real cross-event-loop defect. If G11 is intermittent, it is to be diagnosed with a trace, not stabilized with a timeout. `trace: 'retain-on-failure'` is inherited from the existing config for exactly this.
- **Failure artefacts:** the CI job uploads `playwright-report/` on failure, matching the existing browser job, so a red run on someone else's PR is diagnosable without reproducing it.

---

## Out of scope

- **The stakeholder test-health dashboard.** Agreed as the next piece of work *after* this milestone; it is a product surface (a route, a page, an admin gate) and folding it into a test-infrastructure milestone would mix two trust questions in one review.
- **Any second path.** A failed-negotiation path (`counter → decline`), the fell-through path (`relist`), password reset, saved-search alerts, watchlist and buyer verification all have thorough backend coverage and no place in *the* golden path. This is one narrative; a suite of browser narratives is a different, larger decision.
- **Cross-browser.** Chromium only, matching the existing config. Firefox/WebKit multiply the runtime and CI cost for a class of defect this project has never hit.
- **Mobile viewports.** `layout.spec.ts` already owns responsive assertions at 360/768/1280; duplicating them here would create the second home for a claim that Article 4 warns about.
- **Performance assertions.** The p95 NFR needs a load harness, and that belongs to production hardening (`security.md` §9), not to a functional path.
