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
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
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
