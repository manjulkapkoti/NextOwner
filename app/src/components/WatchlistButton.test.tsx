// M9 — the watchlist toggle button (spec 009 plan § Frontend).
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WatchlistButton } from './WatchlistButton'
import { authStore } from '../stores/authStore'
import { watchlistStore } from '../stores/watchlistStore'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function row(listingId: number) {
  return {
    listing_id: listingId,
    added_at: '2026-07-26T00:00:00Z',
    type: 'saas',
    headline: 'Profitable B2B scheduling SaaS',
    description: 'A small, profitable scheduling tool for clinics.',
    asking_price: '500000.00',
    ttm_revenue: '200000.00',
    ttm_profit: '120000.00',
    mrr: '18000.00',
    churn_pct: '2.50',
    customers: 340,
    published_at: '2026-07-01T00:00:00Z',
  }
}

describe('WatchlistButton', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'a.b.c')
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
    authStore.logout()
    watchlistStore.reset()
  })

  it('renders nothing when logged out (no token)', () => {
    authStore.logout()
    localStorage.clear()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(<WatchlistButton listingId={1} />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('clicking an unwatchlisted listing calls POST /api/watchlist/{id} and flips to watchlisted', async () => {
    authStore.setToken('a.b.c')
    let added = false
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method
      if (url === '/api/watchlist' && !method) {
        return jsonResponse(200, added ? [row(1)] : [])
      }
      if (url === '/api/watchlist/1' && method === 'POST') {
        added = true
        return jsonResponse(201, row(1))
      }
      return jsonResponse(200, [])
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<WatchlistButton listingId={1} />)

    const button = await screen.findByRole('button', { name: /add to watchlist/i })
    await userEvent.click(button)

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/watchlist/1',
        expect.objectContaining({ method: 'POST' }),
      ),
    )
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /remove from watchlist/i })).toBeInTheDocument(),
    )
  })

  it('clicking an already-watchlisted listing calls DELETE /api/watchlist/{id} and flips back', async () => {
    authStore.setToken('a.b.c')
    let removed = false
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method
      if (url === '/api/watchlist' && !method) {
        return jsonResponse(200, removed ? [] : [row(5)])
      }
      if (url === '/api/watchlist/5' && method === 'DELETE') {
        removed = true
        return new Response(null, { status: 204 })
      }
      return jsonResponse(200, [])
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<WatchlistButton listingId={5} />)

    const button = await screen.findByRole('button', { name: /remove from watchlist/i })
    await userEvent.click(button)

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/watchlist/5',
        expect.objectContaining({ method: 'DELETE' }),
      ),
    )
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /add to watchlist/i })).toBeInTheDocument(),
    )
  })
})
