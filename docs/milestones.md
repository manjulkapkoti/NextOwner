# NextOwner — Milestone Runbook

> The repeatable steps to run for **every** milestone, plus the full M0→M12 checklist. This is the "what to run" index — for scope detail see [`design_implementation.md`](./design_implementation.md) Part 4, for the test checklists see [`testing_guide.md`](./testing_guide.md) §5, and for per-milestone security see [`security.md`](./security.md) §7. Per-milestone additions from the 2026-07-16 gap review live in [§ Scope fold-ins](#scope-fold-ins-gap-review-2026-07-16) below — `/new-spec` reads them at spec time.

---

## Run this loop for EVERY milestone

```
1. /start-milestone <slug>     # cut feat/NNN-<slug> off fresh main
2. /new-spec <slug>            # product-lead scopes → spec.md + plan.md (incl. Security & abuse, § Scope fold-ins, and plan.md's Build order)
3. (failing tests first)       # appsec-engineer writes the forbidden-path tests — they FAIL. The red set is now the queue.
4. (implement, slice by slice) # work plan.md's Build order — one trust boundary per slice, one commit each; red count only goes down
5. /dod                        # full `npm test` + the security must-cover matrix → verifies green (NO PR yet)
6. (review + test)             # inline review ON THE BRANCH (+ 1 appsec agent on M1/M2/M5/M7/M8/M10), fix findings
7. (open PR)                   # only after the review is clean → a PR = "vetted, ready for a human"
8. (human review) → "close the feature"   # you approve → squash-merge + sync main → next milestone
```

**Rules:** spec only 1–2 milestones ahead · every GIVEN/WHEN/THEN = one test, written failing first · `main` is updated only via a **green PR** · commit freely on the branch (WIP is fine).

**Automate it:** `/run-milestone <slug>` drives steps 1–7 for you (branch → spec → failing tests → implement → `/dod` green gate → **review & test on the branch** — inline by default, plus one independent `appsec` pass on the security-critical milestones M1/M2/M5/M7/M8/M10 → open the PR once it's clean) and stops at the vetted PR for your review. Add `--pause-after-spec` to approve the spec before it builds. The merge always stays manual — you review, then `/close-feature`.

For example:

- /run-milestone m0-scaffold (then review → "close the feature")
- /run-milestone auth-roles --pause-after-spec

---

## The milestones

⭐ = the crown-jewel security milestone. Spec = the `specs/NNN-*` number (M0 is the scaffold, no spec).

| #         | Run as                                          | Goal                                                                 | Spec | Key security focus                                                                                                                                  |
| --------- | ----------------------------------------------- | -------------------------------------------------------------------- | ---- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **M0**    | `/start-milestone m0-scaffold` → `/scaffold-m0` | Scaffold `app/` + `backend/` + the test harness; prove `GET /health` | —    | `.gitignore` in place, no secrets in code, `/docs` leaks nothing                                                                                    |
| **M1**    | `/start-milestone auth-roles`                   | Register / login / JWT; `get_current_user`, `require_admin`          | 001  | bcrypt, JWT secret from env, pinned alg + expiry, role re-read from DB, login rate-limit, no user-enumeration                                       |
| **M2**    | `/start-milestone listing-builder`              | Seller listing builder (multi-step) + document uploads               | 002  | `owner_id` from JWT, no client self-publish, PUT on another's listing → 403, upload type/size + path confinement                                    |
| **M3**    | `/start-milestone admin-curation`               | Admin curation queue (approve / reject)                              | 003  | `require_admin` (from DB), 409 on illegal transition, no seller path to self-publish                                                                |
| **M4**    | `/start-milestone marketplace-browse`           | Marketplace browse + anonymous cards (filters)                       | 004  | public `response_model` — no identity leak by schema, only `live` listings, pagination cap                                                          |
| **M5** ⭐ | `/start-milestone nda-gate`                     | Platform NDA + access gate (**the trust core**)                      | 005  | every gate state tested (unsigned/none/requested/approved/owner/denied/revoked), unique constraint, seller-only approve, same gate on doc downloads |
| **M6**    | `/start-milestone chat`                         | Realtime WebSocket chat                                              | 006  | authN on connect, membership authZ, sender from token (spoof ignored), XSS-safe render, history → 403 for non-members                               |
| **M7**    | `/start-milestone offers`                       | Offers / LOI                                                         | 007  | approved-access + live required, **atomic** accept (offer + listing), seller-only decisions, 409 on decided, audit rows                             |
| **M8**    | `/start-milestone alerts`                       | Notifications engine + saved searches & alerts + **account lifecycle** *(scope expanded 2026-07-16; account lifecycle moved from M1 2026-07-17)* | 008  | every notification caller-scoped; the fan-out doesn't leak or cross users; **password-reset tokens: single-use, short expiry, hashed at rest, no user-enumeration, never logged** — this is auth surface, hence security-critical |
| **M9**    | `/start-milestone watchlist`                    | Watchlist                                                            | 009  | every operation caller-scoped (you only see/edit your own)                                                                                          |
| **M10**   | `/start-milestone buyer-verification`           | Manual buyer verification                                            | 010  | buyer can't self-verify (`verified` ignored/403), admin-only flip, upload safety                                                                    |
| **M11**   | `/start-milestone valuation-calculator`         | Valuation calculator (lead magnet)                                   | 011  | validate inputs if a `POST /valuation` endpoint is added; no injection                                                                              |
| **M12**   | `/start-milestone deal-completion`              | Deal completion — `under_offer` → sold / fell-through (re-list) + final price | 012  | seller-only transitions, 409 from non-`under_offer`, atomic offer+listing flip, **price derived from the accepted offer**, audit rows, NDA gate unweakened |
| **E2E**   | after Phase D                                   | Playwright golden path: sign-up → gated data → offer → accept → sold (M12) | —    | the full trust chain green = a security regression check                                                                                            |

> **⚠ Not yet sequenced — Payments & monetization.** The subscription / listing-fee **paywall** (at the *contact moment*, so logically ~M6 chat / M7 offers) and **escrow settlement** (post-accept) are **not** yet a numbered milestone. `product-lead` must scope + slot it. The security invariants are already captured (`docs/security.md` § Third-party vendors & webhooks — webhook signatures, idempotency, card/PAN off our servers, server-derived amounts, mock-mirrors-real); real Stripe/Escrow integration + PCI + KYC/AML stay deferred to `legal-compliance`. `docs/error_handling.md`'s Stripe/Escrow failure modes reference this pending milestone. *(2026-07-16: the **mocked** deal-close mechanics — sold / fell-through, invoice, asset-transfer checklist — are now owned by **M12**; this banner covers the real-money half. ⚠ Legal note per the research synthesis, risk #3: "in-platform Stripe escrow for small deals" is money transmission — `legal-compliance` must vet KYC/AML + licensing before any real implementation.)*

> **⚠ Not yet sequenced — Trust & safety / admin operations.** The fraud-report / flag-listing workflow, admin **user management**, and deal monitoring (FR-21, NFR *Trust & safety*) have no owning milestone — M3 builds only the curation queue. Post-MVP is acceptable; unowned is not. `product-lead` to slot alongside the payments milestone (both matter the moment real users arrive).

---

## Scope fold-ins (gap review, 2026-07-16)

Additions from the end-to-end gap review that belong to an **already-sequenced** milestone (recorded in the constitution's amendment log). **`/new-spec` must read this section** when scoping its milestone — each bullet becomes acceptance criteria (plus its forbidden-path twin) in that spec. Cross-cutting doc addenda (security.md, error_handling.md) land with the owning milestone.

- **M1 — auth & roles** *(product-lead may split the account-lifecycle items into a follow-on milestone if M1 balloons)*
  - **Refresh-token decision — RESOLVED 2026-07-17: deferred (owned, not limbo).** M1 ships **access-token-only**; refresh + the httpOnly-cookie session it needs land with deploy hardening (`security.md` §9), triggered by real deployment/users. FR-1 amended deliberately (the fold-in's "amend, don't drift" demand met). **M1's remaining obligation: record the production token-storage approach in the spec** — the seam that keeps refresh a clean later-add.
  - ~~**Account lifecycle:** password reset + email verification~~ — **moved to M8 (2026-07-17).** It was M1's only heavy item and it depends on an email channel M8 builds anyway; the dependency now runs the right way round. See M8's fold-in.
  - **Google OAuth is NOT in M1 — email + password only** (FR-1, marked post-MVP 2026-07-17). Cite FR-1 in the spec **without** its OAuth clause. *Why this is a fold-in and not just a scope note: the deferral was only ever written in `design_implementation.md` Part 4's prose, while the binding FR-1 promised OAuth outright — so the two disagreed and `/new-spec` reads the binding one. The same drift-check that caught FR-1's refresh half (the bullet above) missed its OAuth half.* A hosted provider also needs a cloud project, which Article 1's "100% local — no cloud account" rule excludes.
  - **Both-roles path (FR-2):** how a buyer also becomes a seller (role-upgrade endpoint or role set) — decide + test.
  - **Minimal profiles (FR-3):** display name + buyer fields (budget, target industries, experience); `PUT /profile`. Surfaced later by M5 (FR-14: the seller sees the buyer profile) and M10 (verification badge).
  - **`tos_accepted_at` (+ version)** stamped at registration — a retained legal record, same class as the NDA timestamp.
  - **Settings module owns `DATABASE_URL`** (env via pydantic-settings, per security.md §1.2/§10) — `db.py` stops hardcoding it; `.env.example` ships.
  - **Delete the throwaway `/api/sandbox` + `SandboxItem`** (M0 follow-up — an unauthenticated write path).
  - **Rate-limit behind a swappable backend** (horizontal-scale blocker #1, 2026-07-16 amendment): the in-process counter is the right MVP implementation, but N instances ⇒ N× the limit, so don't hard-wire it — the store must be a config swap to a shared (Redis-class) backend. See `design_implementation.md` § *Horizontal scale*.
  - **Curate `requirements.txt`** as real dependencies arrive: direct deps pinned deliberately, separate from the transitive freeze, so `pip audit` findings map to intentional choices.
  - **Linters land here** — **Ruff** for `backend/`, **ESLint** for `app/`: config, a root `npm run lint` script, and a CI step alongside the existing two jobs. They were meant for M0 and slipped. **Recorded 2026-07-17 after an audit found they were tracked *only in an assistant's memory* and appeared nowhere in the repo** — zero hits across `docs/`, `specs/`, `CLAUDE.md`, `.claude/`. Cheap now; a retrofit across a whole codebase later. *The lesson worth more than the linters: a deferred task that isn't written into the repo isn't deferred — it's forgotten. The repo is the only memory that survives a new tool, a new machine, or a new assistant.*
- **M2 — listing builder**
  - **Money is `Decimal` (or integer cents), never `float`** — asking price, revenue, profit, MRR; record the single-currency (USD) assumption. (Supersedes the `float` sketch in design_implementation §3.5.)
  - **Listing lifecycle (FR-8):** `pause` / `close` transitions; **edits to a `live` listing send it back to `pending_review`** (no bait-and-switch behind curation) — forbidden-path tested.
  - **`GET /my/listings`** dashboard endpoint (M4's public browse deliberately never returns the owner's drafts).
  - **Uploads go through a storage port, not `open()`** (horizontal-scale blocker #2, 2026-07-16 amendment): local disk under `uploads/{listing_id}/` stays the MVP implementation, but routers call a small `save(listing_id, file) → key` / `open(key)` interface so the object-storage (S3-class) swap is one adapter and never touches the permission gate. The path-confinement rules (security.md §6) are the *adapter's* job. See `design_implementation.md` § *Horizontal scale*.
  - Optional: **owner walkthrough `video_url`** field (Baton B4 — "recommended, not yet adopted" in the research decisions ledger).
- **M3 — admin curation**
  - **`listing_event` audit table** (actor, action, reason, timestamp) — the NFR's "immutable audit log of listing state changes"; approve/reject (and later pause/sold) write rows. These rows are also the future golden set for the agentic vetting agent (proposal D).
  - **Emit notification events** (listing approved / rejected) — delivered when M8 lands.
  - **FR-4 gets an owner:** seller-legitimacy review is folded into curation — record it in the spec so FR-4 stops being unmapped.
- **M4 — marketplace browse:** **keyword search** (FR-10 — SQL `LIKE` is fine at MVP) alongside the filters; `seed/seed.py` (~30 listings) arrives here (research synthesis risk #1: seeded supply is not optional polish).
- **M5 — NDA + access gate**
  - **Revocation endpoint** (`approved → revoked`, seller-only) — security.md §7 already requires "revocation re-denies"; this is the endpoint that makes that test possible.
  - **`nda_version`** recorded at signature (know *which* NDA text was signed — it is a retained legal record).
  - **The access-request list shows the buyer profile + verification status** (FR-14 — depends on the M1 profile fold-in).
  - **`GET /my/access-requests`** (buyer side) + emit notification events (requested / approved / denied).
- **M6 — chat:** conversation **unique per (listing, buyer)**; **`last_read_at` per participant** (unread counts); **WebSocket error contract** (close codes for auth-fail / non-member / revocation / rate-cap — lands as an `error_handling.md` addendum); emit message events for the FR-16 email fallback (delivered at M8).
  - **Broadcast behind a `publish(conversation_id, message)` port** (horizontal-scale blocker #3 — the worst of the three, 2026-07-16 amendment): the in-memory `{conversation_id: [sockets]}` dict is single-instance-only *by construction*, and behind a load balancer messages **fail silently** (buyer on instance A, seller on instance B — no error, just no delivery). Keep the dict; keep the routers ignorant of it, so a Redis / Postgres `LISTEN/NOTIFY` backplane drops in later. **Persist → publish → fan out**, in that order. See `design_implementation.md` § *Horizontal scale*.
- **M7 — offers**
  - **Counter-offer model** decided in the spec (a new linked offer row vs. status mutation) + tested — the enum's `countered` is currently behavior-free.
  - **Sibling-offers policy on accept** (auto-decline with notification vs. leave pending) — decide + test; M12 honors it on re-list.
  - **`GET /my/offers`** (buyer) / offers per listing (seller); emit offer events. Offer **expiry** may be deferred post-MVP — say so in the spec.
- **M8 — notifications engine + saved searches** *(scope expanded — constitution amendment 2026-07-16):* deliver **all** events emitted by M3/M5/M6/M7 (in-app inbox + email via MailHog — FR-22 + the FR-16 fallback), plus the saved-search matching fan-out; every delivery caller-scoped.
  - **Account lifecycle — password reset + email verification** *(moved here from M1, 2026-07-17).* M8 **owns the email channel** (SMTP → MailHog at `localhost:8025`), so the recovery flows ship with the machinery that delivers them — the dependency M1's fold-in had backwards ("the channel arrives in M1; M8 reuses it"). **This makes M8 security-critical** (see the ⚠ below): a reset token is account takeover if it leaks, so it needs single-use + short expiry + high entropy, an invariant response whether or not the address exists (no user enumeration — same rule as M1's login), and no token in a log or a URL that a proxy records. Email verification gates nothing until a milestone asks it to; say so explicitly in the spec rather than leaving it implied.
  - ⚠ **Consequence to accept knowingly:** M1–M7 ship with **no self-serve password reset and no verified addresses**. Fine while the build is 100% local with no real users (reset in SQLite); **not** fine the moment anyone real signs up. If the plan changes and real users arrive before M8, this fold-in moves back — it is a scoping call, not an architectural one.
- **M10 — buyer verification:** the badge surfaces on the M1 profile (and in M5's request list); add a **per-listing upload count / total-size quota** (extends the M2 upload rules; security.md §6 addendum).
- **M11 — valuation calculator:** **email lead capture** (FR-23's business half — the calculator exists to capture seller leads) — or explicitly de-scope it in the spec.
- **M12 — deal completion:** a new milestone, not a fold-in — see the table row, `design_implementation.md` Part 4 (Milestone 12), `testing_guide.md` §5, `security.md` §7.

---

## Progress tracker

- [x] **M0** — scaffold + `GET /health`
- [ ] **M1** — auth & roles *(+ account lifecycle, profiles, ToS stamp — § Scope fold-ins)*
- [ ] **M2** — listing builder + uploads *(+ lifecycle transitions, `Decimal` money — § Scope fold-ins)*
- [ ] **M3** — admin curation *(+ `listing_event` audit — § Scope fold-ins)*
- [ ] **M4** — marketplace browse *(+ keyword search, seed data — § Scope fold-ins)*
- [ ] **M5** ⭐ — NDA + access gate *(+ revocation endpoint, `nda_version` — § Scope fold-ins)*
- [ ] **M6** — realtime chat *(+ unread counts, WS error contract — § Scope fold-ins)*
- [ ] **M7** — offers / LOI *(+ counter model, sibling policy — § Scope fold-ins)*
- [ ] **M8** — notifications engine + saved searches & alerts *(scope expanded)*
- [ ] **M9** — watchlist
- [ ] **M10** — buyer verification *(+ badge on profile, upload quota — § Scope fold-ins)*
- [ ] **M11** — valuation calculator *(+ lead capture — § Scope fold-ins)*
- [ ] **M12** — deal completion *(sold / fell-through + final price)*
- [ ] **E2E** — Playwright golden path *(extends to "sold" once M12 lands)*
- [ ] **⚠ Payments & monetization** — subscription/listing-fee paywall + escrow settlement · **not yet sequenced** (`product-lead` to slot, ~M6–M7)
- [ ] **⚠ Trust & safety / admin ops** — fraud reports, user management, deal monitoring (FR-21) · **not yet sequenced** (`product-lead` to slot)

_Milestone order M0→M12 is binding (constitution Article 3; M12 appended 2026-07-16). Boxes tick automatically as part of `/dod` step 6's pre-PR commit (see `docs/session_recovery.md`), so a box is checked the instant its PR merges._
