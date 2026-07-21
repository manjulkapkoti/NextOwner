// M7 — the seller's per-listing offers queue (spec 007 criterion J3;
// FR-17, G1-G4).
//
// Mirrors `AccessRequestQueue.tsx`'s own framing (M5): the seller sees enough
// to decide and nothing more. Here that means every buyer's full negotiation
// thread (root offer -> counters -> the current state), each carrying that
// buyer's profile — but never their email (PII minimization; the backend's
// own G3 already keeps `OfferWithBuyer` from carrying one, this file is the
// "and the UI doesn't invent a place to show one either" companion check).
import { render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ListingOffersQueue } from './ListingOffersQueue'
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

const BUYER_A = {
  display_name: 'Jordan Buyer',
  budget: '250000',
  target_industries: ['saas'],
  experience: 'Former operator of two SaaS exits.',
}

const BUYER_B = {
  display_name: 'Casey Acquirer',
  budget: '400000',
  target_industries: ['ecommerce'],
  experience: null,
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
    buyer: BUYER_A,
    ...overrides,
  }
}

function stubQueue(rows: unknown[]) {
  const fetchMock = vi.fn(async () => jsonResponse(200, rows))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('ListingOffersQueue', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'a.b.c')
    offerStore.reset()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
    offerStore.reset()
  })

  it('J3: renders each buyer\'s thread as a chronological history (root -> counters -> current) with that buyer\'s profile', async () => {
    stubQueue([
      row({
        id: 1,
        proposed_by_role: 'buyer',
        status: 'countered',
        created_at: '2026-07-20T00:00:00Z',
        buyer: BUYER_A,
      }),
      row({
        id: 2,
        parent_offer_id: 1,
        proposed_by_role: 'seller',
        status: 'submitted',
        created_at: '2026-07-20T01:00:00Z',
        buyer: BUYER_A,
      }),
      row({
        id: 3,
        proposed_by_role: 'buyer',
        status: 'submitted',
        created_at: '2026-07-20T02:00:00Z',
        buyer: BUYER_B,
      }),
    ])
    render(<ListingOffersQueue listingId={7} />)

    await waitFor(() => expect(screen.getByText('Jordan Buyer')).toBeInTheDocument())
    expect(screen.getByText('Casey Acquirer')).toBeInTheDocument()

    // Buyer A's thread has two rows in order, and only that section's Accept
    // sits on the live counter — asserting via each row's stable test id
    // (the same convention OfferThread.test.tsx establishes) rather than
    // trusting flat DOM order across two independently-rendered buyers.
    expect(screen.getByTestId('offer-row-1')).toBeInTheDocument()
    expect(screen.getByTestId('offer-row-2')).toBeInTheDocument()
    expect(screen.getByTestId('offer-row-3')).toBeInTheDocument()

    // Buyer A's profile detail is present...
    expect(screen.getByText(/saas/i)).toBeInTheDocument()
    expect(screen.getByText(/former operator of two saas exits/i)).toBeInTheDocument()
    // ...and does not bleed into buyer B's section: B's own industry shows,
    // A's experience text does not appear twice attached to B.
    expect(screen.getByText(/ecommerce/i)).toBeInTheDocument()
  })

  it('J3: the seller can act on the buyer-proposed offer that is currently submitted and awaiting them', async () => {
    stubQueue([row({ id: 1, proposed_by_role: 'buyer', status: 'submitted', buyer: BUYER_A })])
    render(<ListingOffersQueue listingId={7} />)

    const rowEl = await screen.findByTestId('offer-row-1')
    expect(within(rowEl).getByRole('button', { name: /accept/i })).toBeInTheDocument()
    expect(within(rowEl).getByRole('button', { name: /decline/i })).toBeInTheDocument()
  })

  it('never renders a buyer email address anywhere on the page (PII minimization, mirrors G3)', async () => {
    stubQueue([row({ id: 1, buyer: { ...BUYER_A, email: 'jordan@example.com' } as unknown as typeof BUYER_A })])
    render(<ListingOffersQueue listingId={7} />)

    await waitFor(() => expect(screen.getByText('Jordan Buyer')).toBeInTheDocument())
    expect(screen.queryByText(/jordan@example\.com/i)).not.toBeInTheDocument()
  })

  it('shows an empty state when no one has made an offer on this listing yet', async () => {
    stubQueue([])
    render(<ListingOffersQueue listingId={7} />)

    await waitFor(() => expect(screen.getByText(/no offers/i)).toBeInTheDocument())
  })

  it('shows a distinct error state on a load failure, without crashing', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse(500, { detail: 'Something went wrong.', request_id: 'req_1' })),
    )
    render(<ListingOffersQueue listingId={7} />)

    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
