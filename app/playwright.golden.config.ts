// Playwright — the golden path (spec 013, Phase D).
//
// A SEPARATE config from playwright.config.ts, deliberately (spec 013 D3). That
// one starts `vite preview` and nothing else, and its suites stub every API call
// with `page.route`. Adding a Python backend to its `webServer` array would make
// `npm run e2e:a11y` — the tight UI loop — depend on a virtualenv and a
// database. So the golden path gets its own runner, and the two can never flake
// into each other.
//
// What makes this run trustworthy, and what would silently destroy it:
//   - a REAL backend on a DEDICATED database (D2/D7) — see `webServer` below;
//     the database is deleted before uvicorn opens it, by scripts/e2e_serve.py
//   - `reuseExistingServer: false` — reusing a server means reusing its rows,
//     and every "unique headline" assumption (D10) stops holding
//   - `retries: 0` — a step that needs a retry is reporting a real race in the
//     product, and hiding it is the opposite of what this suite is for
import { defineConfig, devices } from '@playwright/test'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

const API_PORT = 8001 // not 8000: that port is commonly taken on dev machines
const PREVIEW_PORT = 4174 // not 4173: the UI config's, so both can run at once
export const BASE_URL = `http://localhost:${PREVIEW_PORT}`
export const API_URL = `http://127.0.0.1:${API_PORT}`

// H1 — the whole run writes here and nowhere else. Relative to the backend cwd
// set on the server below, so it lands at backend/e2e.db (gitignored).
// scripts/e2e_serve.py refuses to start if this ever names nextowner.db.
const DATABASE_URL = 'sqlite:///e2e.db'

// The venv on a dev machine, plain `python` in CI. Resolved here rather than
// asked of the developer, because a config that needs an env var set correctly
// is a config that fails confusingly the first time someone clones the repo.
export const REPO_ROOT = resolve(import.meta.dirname, '..')
export const BACKEND_DIR = resolve(REPO_ROOT, 'backend')
export const PYTHON =
  [
    resolve(BACKEND_DIR, '.venv', 'Scripts', 'python.exe'), // Windows
    resolve(BACKEND_DIR, '.venv', 'bin', 'python'), // POSIX
  ].find(existsSync) ?? 'python'

// Auth rate limits, raised for this run only (see § Recorded deviation in
// specs/013-e2e-golden-path/plan.md). The limiter is keyed per IP, and every
// session in this suite arrives from localhost: the path performs ~8 logins
// against a production default of 5/minute, so the suite would fail on a
// control it does not test and pre-011 already covers. Raised, not disabled —
// the limiter is still wired in, so a bug that removed it entirely is still
// observable. Nothing else about the backend is reconfigured.
const RELAXED_AUTH_LIMITS = {
  LOGIN_RATE_LIMIT_MAX: '200',
  REGISTER_RATE_LIMIT_MAX: '200',
}

export default defineConfig({
  testDir: './e2e',
  // The golden files and nothing else. Without this the UI suites (which stub
  // every request) would be pulled into a run whose entire point is that
  // nothing is stubbed.
  testMatch: /golden-path(\.guards)?\.spec\.ts$/,
  // Deliberately not `process.env.CI ? 2 : 0` — see the header. This is the one
  // suite in the repo where a retry would hide the defect it exists to find.
  retries: 0,
  // One worker: the path is one narrative against one database, and the trust
  // checks arrange rows in the same one. Parallel workers would interleave
  // registrations against a shared backend for no gain — there are four tests.
  workers: 1,
  timeout: 90_000,
  reporter: process.env.CI ? [['github'], ['list']] : [['list']],
  // Registers the admin through the real API and promotes it with the CLI
  // (D5/D6). Runs after the servers are up — it needs both.
  globalSetup: './e2e/support/golden-global-setup.ts',
  use: {
    baseURL: BASE_URL,
    // G11 (WebSocket delivery across two contexts) is the step most likely to
    // fail intermittently, and spec 013 § Errors is explicit that such a
    // failure is to be diagnosed with a trace, not stabilized with a timeout.
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      // Deletes e2e.db, then serves. One process, so the order is a fact of the
      // code rather than an assumption about Playwright's startup sequence.
      command: `"${PYTHON}" ../scripts/e2e_serve.py`,
      cwd: BACKEND_DIR,
      url: `${API_URL}/api/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: 'pipe',
      env: {
        DATABASE_URL,
        E2E_API_PORT: String(API_PORT),
        // Off, or every registration in the run tries to reach an SMTP server
        // that is not running and the suite times out on mail, not on product.
        EMAIL_ENABLED: 'false',
        ...RELAXED_AUTH_LIMITS,
      },
    },
    {
      // The BUILT bundle, same reason the UI config gives: it is what ships.
      // `vite preview` does not read `server.proxy`, so vite.config.ts grows a
      // matching `preview.proxy` block (D4) pointed here by E2E_API_PORT.
      command: `npm run build && npm run preview -- --port ${PREVIEW_PORT} --strictPort`,
      url: BASE_URL,
      reuseExistingServer: false,
      timeout: 180_000,
      env: { E2E_API_PORT: String(API_PORT) },
    },
  ],
})
