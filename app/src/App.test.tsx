import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

// Milestone 0 — proves the component harness works and the health page renders
// the API result. fetch is stubbed so the test never needs a live backend.
describe('App health page', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ status: 'ok' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
      ),
    )
  })

  afterEach(() => vi.unstubAllGlobals())

  it('shows the health status returned by GET /api/health', async () => {
    render(<App />)
    await waitFor(() =>
      expect(screen.getByText(/API health: ok/i)).toBeInTheDocument(),
    )
    // Relative, same-origin URL — the /api prefix is always present in code.
    expect(fetch).toHaveBeenCalledWith('/api/health', expect.any(Object))
  })

  it('shows an error banner when the API is unreachable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new Error('network down')
      }),
    )
    render(<App />)
    await waitFor(() =>
      expect(screen.getByText(/API unreachable/i)).toBeInTheDocument(),
    )
  })
})
