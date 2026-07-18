// Playwright — the visual and accessibility loop.
//
// This exists because an agent building UI is otherwise blind: every visual
// defect this project hit (a duplicated logo mark, a nav that wrapped on a
// phone, buttons undersized against the wordmark, a ring sitting 1px off the
// baseline) had to be spotted by a human and described back. These specs let
// the work be *looked at* before a human is asked to look at it.
//
// Two suites, different jobs:
//   e2e/screens.spec.ts — captures every screen at three widths (artefacts,
//                         not assertions; they are there to be read)
//   e2e/a11y.spec.ts    — axe-core assertions, which DO fail the run
//
// It drives the built app via `vite preview`, not the dev server: the built
// bundle is what ships, and a dev-only failure would be a false alarm.
import { defineConfig, devices } from '@playwright/test'

const PORT = 4173
export const BASE_URL = `http://localhost:${PORT}`

export default defineConfig({
  testDir: './e2e',
  // Screens are captured for reading, so a flake wastes a human's attention
  // rather than failing a build; retry once locally, twice in CI.
  retries: process.env.CI ? 2 : 1,
  reporter: process.env.CI ? [['github'], ['list']] : [['list']],
  use: {
    baseURL: BASE_URL,
    // Only on failure — a passing a11y run has nothing to look at.
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run build && npm run preview -- --port ' + PORT,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
})
