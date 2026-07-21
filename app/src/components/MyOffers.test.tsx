// M7 — the buyer's own cross-listing offers dashboard (spec 007, plan.md §
// Frontend). Named in plan.md but not tied to its own lettered J-criterion —
// J1/J2 (spec 007) cover the single-listing panel (`OfferForm`) and J3 covers
// the seller's per-listing queue; this is the buyer-side mirror of the
// backend's own F1-F3 reads ("GET /api/my/offers" — every thread across every
// listing, caller-scoped), and user story 8 ("As either party, I want to see
// the full history of offers and counters"). Flagged in the handoff report as
// a spec point worth a name if a future spec wants to test it more strictly.
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MyOffers } from './MyOffers'
import { offerStore } from '../stores/offerStore'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const TERMS = {
  price: '250000.00',
  structure: 'all cash',
  contingencies: 'subject to financing',
  proposed_close_date: '2026-09-01',
}

function row(overrides: Record<string, unknown>) {
  return {
    id: 1,
    listing_id: 7,
    parent_offer_id: null,
    proposed_by_role: 'buyer',
    status: 'submitted',
    ...TERMS,
    created_at: '2026-07-20T00:00:00Z',
    decided_at: null,
    ...overrides,
  }
}

function stubMine(rows: unknown[]) {
  vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, rows)))
}

describe('MyOffers', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'a.b.c')
    offerStore.reset()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
    offerStore.reset()
  })

  it('renders every offer thread across every listing the buyer has offers on (FR-17, user story 8)', async () => {
    stubMine([
      row({ id: 1, listing_id: 7, created_at: '2026-07-20T00:00:00Z' }),
      row({ id: 2, listing_id: 9, created_at: '2026-07-20T01:00:00Z' }),
    ])
    render(<MyOffers />)

    await waitFor(() => expect(screen.getByTestId('offer-row-1')).toBeInTheDocument())
    expect(screen.getByTestId('offer-row-2')).toBeInTheDocument()
    // Two separate listings — the thread for one must not swallow the other.
    expect(screen.getByText(/7/)).toBeInTheDocument()
    expect(screen.getByText(/9/)).toBeInTheDocument()
  })

  it('groups a multi-row chain (root + counter) under the one listing it belongs to, in order', async () => {
    stubMine([
      row({ id: 1, listing_id: 7, status: 'countered', created_at: '2026-07-20T00:00:00Z' }),
      row({
        id: 2,
        listing_id: 7,
        parent_offer_id: 1,
        status: 'submitted',
        proposed_by_role: 'seller',
        created_at: '2026-07-20T01:00:00Z',
      }),
    ])
    render(<MyOffers />)

    await waitFor(() => expect(screen.getByTestId('offer-row-1')).toBeInTheDocument())
    expect(screen.getByTestId('offer-row-2')).toBeInTheDocument()
  })

  it('shows an empty state when the buyer has never made an offer', async () => {
    stubMine([])
    render(<MyOffers />)

    await waitFor(() => expect(screen.getByText(/no offers|haven.t made/i)).toBeInTheDocument())
  })

  it('shows a distinct error state on a load failure, without crashing', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse(500, { detail: 'Something went wrong.', request_id: 'req_1' })),
    )
    render(<MyOffers />)

    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
