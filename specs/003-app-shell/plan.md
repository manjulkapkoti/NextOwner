# Plan 003 — App Shell

> The *how* for [`spec.md`](./spec.md). Frontend-only; no backend, no schema, no new API.

---

## Components touched (`app/src/`)

- **`App.tsx`** — rewritten from the M0 health page into the routed shell: `BrowserRouter` → an `AppShell` that renders the nav, the global-401 listener, and the routes. Export the inner `AppShell` (or an `AppRoutes`) so tests can mount it under `MemoryRouter`.
- **`components/NavBar.tsx`** *(new)* — a minimal MUI `AppBar`: brand + links to the seller flows when authed, and a **Logout** button (clears `authStore` → `/login`). Reads auth state from `authStore` (MobX `observer`).
- **`main.tsx`** — already wraps `<App/>` in `<ErrorBoundary>`; unchanged beyond that.
- **Reused as-is:** `LoginForm`, `RequireAuth`, `MyListings`, `ListingWizard`, `authStore`, `api.ts` (which already emits `auth:unauthorized` on a 401 — M1).

## Routes

| Path | Element | Guard |
|---|---|---|
| `/login` | `LoginForm`; **redirect to `/my-listings` if already authed** (AS3) | public |
| `/` | redirect to `/my-listings` | `RequireAuth` |
| `/my-listings` | `MyListings` (the landing/dashboard) | `RequireAuth` |
| `/sell` | `ListingWizard` | `RequireAuth` |
| `*` | redirect to `/` | — |

`RequireAuth` (from M1) already redirects a tokenless visitor to `/login` — it just needs to live inside a real router now (AS1, AS2).

## Global 401 handling

An effect in `AppShell` listens for the `auth:unauthorized` window event (emitted by `api.ts` on any 401) and, when it fires, clears the session (`authStore.logout()`) and `navigate("/login")` (AS4). This is the integration `api.ts` was built to plug into (M1 finding #5 / #6 closed here).

## Tests (`app/src/`)

- `App.test.tsx` — **replaces** the M0 health test; covers AS1–AS4, AS6 by mounting `AppShell` under `MemoryRouter` with the appropriate token/`fetch` stubs.
- `components/NavBar.test.tsx` *(new)* — AS5 (logout control visible when authed; logout clears + returns to login).

---

## Build order

**Ordered slices — frontend only.** No checkboxes; the red tests are the status.

| # | Slice | Turns green | Why here |
|---|---|---|---|
| 1 | **Router shell** — `App.tsx` → `BrowserRouter` + routes + `RequireAuth`; replaces the M0 health page and its test | AS1, AS2, AS3, AS6 | The skeleton everything else hangs on; do the routes first |
| 2 | **Global 401 listener** — `AppShell` effect on `auth:unauthorized` → logout + redirect | AS4 | Needs the router (1) for `navigate` |
| 3 | **NavBar + logout** — MUI `AppBar`, auth-aware, Logout control | AS5 | Needs the shell + authStore |

**If a slice reveals the order is wrong, fix this table and say so in the commit.** Never reorder by weakening a test.
