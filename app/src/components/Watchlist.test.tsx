// M9 — the watchlist page (spec 009 plan § Frontend).
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Watchlist } from './Watchlist'
import { authStore } from '../stores/authStore'
import { watchlistStore } from '../stores/watchlistStore'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderWatchlist() {
  return render(
    <MemoryRouter>
      <Watchlist />
    </MemoryRouter>,
  )
}

const ROW = {
  listing_id: 9,
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

describe('Watchlist', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'a.b.c')
    authStore.setToken('a.b.c')
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
    authStore.logout()
    watchlistStore.reset()
  })

  it('shows the empty state when the watchlist has no entries', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, [])))

    renderWatchlist()

    await waitFor(() => expect(screen.getByText(/your watchlist is empty/i)).toBeInTheDocument())
  })

  it('shows entries once loaded', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, [ROW])))

    renderWatchlist()

    await waitFor(() =>
      expect(screen.getByText(/profitable b2b scheduling saas/i)).toBeInTheDocument(),
    )
    // The mapped card shows the asking price too — identifies the listing
    // beyond just its headline.
    expect(screen.getByText(/\$500,000/)).toBeInTheDocument()
  })

  it('shows an error alert when the load fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(500, { detail: 'Internal error' })))

    renderWatchlist()

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})
