# Spec pre-003 — App Shell (frontend foundation)

> **Milestone:** App Shell — a small **foundation** milestone inserted between M2 and M3. Its folder is `specs/pre-003-app-shell/`: the `pre-003` prefix keeps it out of the `NNN` spec sequence, so **M3 stays spec 003** and nothing renumbers (see the milestones runbook + constitution amendment 2026-07-18).
> **Complies with:** [`specs/000-constitution.md`](../000-constitution.md).
> **Not security-critical:** frontend-only, no new backend trust boundary. Client routing is **UX only** — the server permission gates remain the real boundary (`security.md` §Frontend session). No appsec pass needed.
> **Status:** awaiting approval.

---

## Why this milestone exists

M1 and M2 each shipped real, tested frontend components (`LoginForm`, `RequireAuth`, `ErrorBoundary`, `authStore`, `ListingWizard`, `MyListings`) — but **nothing is wired into a running app.** `App.tsx` is still the Milestone-0 health page: no router, no `/login`, no way to click through anything. This milestone assembles those pieces into a usable, navigable app so that (a) the flows can actually be exercised, (b) M3+ add a route to a working router instead of producing another orphaned component, and (c) the Phase-D E2E has a real app to drive.

No backend changes. No new components — only the shell that connects the ones that exist.

## FR references

Serves the client-side half of **FR-1/FR-2** (auth session + navigation) and **FR-5/FR-8** (reaching the seller flows). It ships no new capability of its own — it makes the already-built ones reachable.

---

## User stories

1. **As a visitor,** I want to land on a login page and, once signed in, reach the app, so that I can actually use it.
2. **As a signed-in seller,** I want to navigate to the listing builder and my dashboard, so that the M2 flows are reachable.
3. **As any user,** I want to be sent back to login when my session expires, so that I'm never stuck on a dead page.
4. **As a signed-in user,** I want a visible way to log out.

---

## Acceptance criteria

**Each = exactly one test, written failing first.** Router tests use `MemoryRouter`; `MyListings` renders behind a stubbed `fetch` returning `[]`.

- **AS1** — GIVEN no session (no token), WHEN navigating to `/sell`, THEN the **login page** is shown (the guard redirected).
- **AS2** — GIVEN no session, WHEN navigating to `/my-listings`, THEN the **login page** is shown.
- **AS3** — GIVEN a session (token present), WHEN navigating to `/login`, THEN the user is **redirected to the landing** (`/my-listings`) — the login form is *not* shown.
- **AS4** — GIVEN the app is mounted, WHEN an `auth:unauthorized` event fires (what `api.ts` emits on any 401), THEN the app **navigates to `/login`** and the token is cleared.
- **AS5** — GIVEN a session, WHEN the shell renders, THEN a **Logout** control is visible; clicking it **clears the session** and returns to `/login`.
- **AS6** — GIVEN a session, WHEN navigating to `/` (the landing), THEN the seller's **dashboard** (`MyListings`) renders.
- **AS8** *(added post-merge, 2026-07-18)* — GIVEN no session, WHEN navigating to `/register`, THEN the **registration form** renders. New `RegisterForm` component (FR-1/FR-2: email, password, role) — the register *endpoint* existed since M1, but nothing let a visitor reach it.
- **AS9** *(added post-merge, 2026-07-18)* — GIVEN a session, WHEN navigating to `/register`, THEN the visitor is **redirected to the dashboard** — same already-authed treatment as `/login` (AS3).

## Out of scope (deferred)

- **Public/marketing pages** — the anonymous browse experience is **M4**; this shell only routes the authed app + login.
- **Buyer-specific navigation / data room** — M5+.
- **Admin routes** — added by **M3** onto this shell.
- **A polished nav/design system** — minimal MUI `AppBar` here; the design system is a later concern.

## Note: the M0 health page is replaced

`App.tsx` (the M0 "API health" page) becomes the routed shell, and its test (`App.test.tsx`) is **replaced** by the shell tests above — a deliberate criterion, not silent deletion (the backend `/health` *endpoint* is untouched; only the throwaway page goes). This is sequenced as the first Build-order slice.
