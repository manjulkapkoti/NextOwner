/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
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
  },
})
