// Global setup for the golden path (spec 013 D5/D6): make one admin exist.
//
// Admin is granted by a CLI and never by an endpoint. `security.md` §6 names
// "test-only backdoors in prod" as an explicit threat, and an env-flag-gated
// bootstrap route is one — a flag misread in one environment grants admin over
// HTTP forever. So this does what a human operator would do:
//
//   1. register the account through the REAL, rate-limited /api/auth/register
//   2. promote that existing row with seed/make_admin.py
//
// Step 1 is what makes step 2 safe to own: `make_admin` can only ever flip a
// bit on a row that already registered normally (D6), so it cannot inject a
// principal even if it is pointed somewhere it should not be.
import { spawnSync } from 'node:child_process'
import { API_URL, BACKEND_DIR, PYTHON, REPO_ROOT } from '../../playwright.golden.config'

const ADMIN_EMAIL = 'admin@e2e.example.com'
const PASSWORD = 'correct horse battery staple'

// The backend serves with cwd=backend, so its relative `sqlite:///e2e.db`
// lands there. This process runs from the repo root, so the SAME file has to be
// named absolutely — a relative URL here would silently create a SECOND, empty
// database at the root and promote an admin nobody can log in as.
const DATABASE_URL = `sqlite:///${BACKEND_DIR.replace(/\\/g, '/')}/e2e.db`

async function waitForApi(timeoutMs = 60_000): Promise<void> {
  const deadline = Date.now() + timeoutMs
  let lastError = 'never attempted'
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${API_URL}/api/health`)
      if (response.ok) return
      lastError = `HTTP ${response.status}`
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error)
    }
    await new Promise((r) => setTimeout(r, 250))
  }
  throw new Error(
    `[golden setup] the API never came up at ${API_URL} (last: ${lastError}).\n` +
      'If this is the first run after a change to playwright.golden.config.ts, check that ' +
      'globalSetup still runs AFTER webServer — this step needs a live backend to register against.',
  )
}

async function globalSetup(): Promise<void> {
  await waitForApi()

  // 201 on a fresh database; a 4xx means the row is already there, which is
  // fine — `make_admin` below is idempotent and this is the only thing we need.
  const response = await fetch(`${API_URL}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: ADMIN_EMAIL, password: PASSWORD, role: 'buyer' }),
  })
  if (!response.ok && response.status !== 409 && response.status !== 400) {
    throw new Error(
      `[golden setup] could not register ${ADMIN_EMAIL}: HTTP ${response.status} ${await response.text()}`,
    )
  }

  const promotion = spawnSync(PYTHON, ['-m', 'seed.make_admin', ADMIN_EMAIL], {
    cwd: REPO_ROOT,
    encoding: 'utf-8',
    env: {
      ...process.env,
      DATABASE_URL,
      // The explicit opt-in the CLI refuses to run without (H4).
      NEXTOWNER_ALLOW_ADMIN_PROMOTION: '1',
    },
  })
  if (promotion.status !== 0) {
    throw new Error(
      `[golden setup] make_admin failed (exit ${promotion.status}):\n` +
        `${promotion.stdout ?? ''}${promotion.stderr ?? ''}`,
    )
  }
  process.stdout.write(`[golden setup] ${promotion.stdout}`)
}

export default globalSetup
