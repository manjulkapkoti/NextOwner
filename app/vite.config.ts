// `defineConfig` comes from `vitest/config`, not `vite` — it is vite's own
// export re-typed to include the `test` key. On vitest 2 this file needed a
// cast instead, because vitest 2 shipped a nested vite 5 and its module
// augmentation landed on that copy rather than the top-level vite 6. The
// vitest 3 upgrade (2026-07-19) removed that split, so the cast is gone.
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Single-origin dev (design_implementation.md §3.4): the browser talks only to
// the Vite server, which proxies /api and /ws to FastAPI — so there is no CORS
// and dev mirrors the production reverse-proxy layout exactly.
// One proxy table, used by BOTH the dev server and `vite preview` (spec 013
// D4). `vite preview` does not read the `server` key, so before this the built
// bundle had no path to the API at all — which is invisible to `vite dev` and
// to Vitest, and fatal to the golden path, which drives the built bundle.
// Defined once rather than twice so the two cannot drift apart.
//
// The port is fixed at 8000 for ordinary local development. The golden-path
// run sets E2E_API_PORT so its preview server talks to its own hermetic
// backend instead of whatever happens to be on 8000.
const API_PORT = process.env.E2E_API_PORT ?? '8000'
const proxy = {
  '/api': `http://localhost:${API_PORT}`,
  '/ws': { target: `ws://localhost:${API_PORT}`, ws: true },
}

export default defineConfig({
  plugins: [react()],
  server: { proxy },
  preview: { proxy },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.ts',
    // Vitest's 5s default is too tight for this stack. A form test that renders
    // MUI in jsdom, types into two fields and awaits a route change legitimately
    // costs ~4s, so the default left ~800ms of headroom and the suite failed
    // roughly one run in five — which reads as flakiness but was simply being
    // over budget. The per-keystroke delay (the avoidable half) is removed in
    // the tests themselves; this covers the half that is real work.
    testTimeout: 15_000,
    // Unit tests only. Vitest's default glob would also match `e2e/*.spec.ts`,
    // which are Playwright specs — they need a real browser and would fail
    // under jsdom.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
  },
})
