import { defineConfig, type UserConfig } from 'vite'
import react from '@vitejs/plugin-react'
import type { ViteUserConfig } from 'vitest/config'

// Single-origin dev (design_implementation.md §3.4): the browser talks only to
// the Vite server, which proxies /api and /ws to FastAPI — so there is no CORS
// and dev mirrors the production reverse-proxy layout exactly.
//
// The `test` block needs the cast below: vitest 2.1 ships its own nested
// vite 5, so `vitest/config`'s module augmentation lands on that copy — never
// on the top-level vite 6 this file imports from — and a cold `tsc -b`
// rejects `test`. The root fix is the vitest 3 upgrade (single vite 6);
// drop the cast then.
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
  },
} as UserConfig & Pick<ViteUserConfig, 'test'>)
