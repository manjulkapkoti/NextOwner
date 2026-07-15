# NextOwner — Milestone Runbook

> The repeatable steps to run for **every** milestone, plus the full M0→M11 checklist. This is the "what to run" index — for scope detail see [`design_implementation.md`](./design_implementation.md) Part 4, for the test checklists see [`testing_guide.md`](./testing_guide.md) §5, and for per-milestone security see [`security.md`](./security.md) §7.

---

## Run this loop for EVERY milestone

```
1. /start-milestone <slug>     # cut feat/NNN-<slug> off fresh main
2. /new-spec <slug>            # product-lead scopes → spec.md + plan.md (incl. a Security & abuse section)
3. (failing tests first)       # appsec-engineer writes the forbidden-path tests — they FAIL
4. (implement)                 # backend-engineer / frontend-engineer build until the tests pass
5. /dod                        # full `npm test` + the security must-cover matrix → verifies green (NO PR yet)
6. (review + test)             # inline review ON THE BRANCH (+ 1 appsec agent on M1/M2/M5/M7/M10), fix findings
7. (open PR)                   # only after the review is clean → a PR = "vetted, ready for a human"
8. (human review) → "close the feature"   # you approve → squash-merge + sync main → next milestone
```

**Rules:** spec only 1–2 milestones ahead · every GIVEN/WHEN/THEN = one test, written failing first · `main` is updated only via a **green PR** · commit freely on the branch (WIP is fine).

**Automate it:** `/run-milestone <slug>` drives steps 1–7 for you (branch → spec → failing tests → implement → `/dod` green gate → **review & test on the branch** — inline by default, plus one independent `appsec` pass on the security-critical milestones M1/M2/M5/M7/M10 → open the PR once it's clean) and stops at the vetted PR for your review. Add `--pause-after-spec` to approve the spec before it builds. The merge always stays manual — you review, then `/close-feature`.

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
| **M8**    | `/start-milestone alerts`                       | Saved searches & alerts                                              | 008  | notifications caller-scoped, the background fan-out doesn't leak or cross users                                                                     |
| **M9**    | `/start-milestone watchlist`                    | Watchlist                                                            | 009  | every operation caller-scoped (you only see/edit your own)                                                                                          |
| **M10**   | `/start-milestone buyer-verification`           | Manual buyer verification                                            | 010  | buyer can't self-verify (`verified` ignored/403), admin-only flip, upload safety                                                                    |
| **M11**   | `/start-milestone valuation-calculator`         | Valuation calculator (lead magnet)                                   | 011  | validate inputs if a `POST /valuation` endpoint is added; no injection                                                                              |
| **E2E**   | after Phase D                                   | Playwright golden path: sign-up → gated data → offer → accept        | —    | the full trust chain green = a security regression check                                                                                            |

---

## Progress tracker

- [ ] **M0** — scaffold + `GET /health`
- [ ] **M1** — auth & roles
- [ ] **M2** — listing builder + uploads
- [ ] **M3** — admin curation
- [ ] **M4** — marketplace browse
- [ ] **M5** ⭐ — NDA + access gate
- [ ] **M6** — realtime chat
- [ ] **M7** — offers / LOI
- [ ] **M8** — saved searches & alerts
- [ ] **M9** — watchlist
- [ ] **M10** — buyer verification
- [ ] **M11** — valuation calculator
- [ ] **E2E** — Playwright golden path

_Milestone order M0→M11 is binding (constitution Article 3). Tick each box when its PR is merged and `main` is green._
