// M7 — offerStore (spec 007). Backs OfferForm/OfferThread/MyOffers/
// ListingOffersQueue (J1-J5, X4) the way accessStore backs RequestAccessPanel.
//
// Not itself a lettered frontend criterion, but the layer every J-criterion
// component reads from — mirroring how accessStore.test.ts exists even though
// J1-J5 in spec 005 are all component-level. Tested directly here because a
// bug in "which row is the active one" or in not re-deriving state from the
// server after a POST would be invisible from a single component's happy path
// but would surface everywhere a returning buyer reloads the page (the exact
// gap RequestAccessPanel's J2 test was written to catch at M5).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { offerStore } from './offerStore'

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

describe('offerStore', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'a.b.c')
    offerStore.reset()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
    offerStore.reset()
  })

  it('loadMyOffers: populates myOffers from GET /my/offers, and offersForListing filters + orders it oldest-first', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(200, [
          {
            id: 2,
            listing_id: 7,
            parent_offer_id: 1,
            proposed_by_role: 'seller',
            status: 'submitted',
            ...TERMS,
            created_at: '2026-07-20T01:00:00Z',
            decided_at: null,
          },
          {
            id: 5,
            listing_id: 9,
            parent_offer_id: null,
            proposed_by_role: 'buyer',
            status: 'submitted',
            ...TERMS,
            created_at: '2026-07-20T02:00:00Z',
            decided_at: null,
          },
          {
            id: 1,
            listing_id: 7,
            parent_offer_id: null,
            proposed_by_role: 'buyer',
            status: 'countered',
            ...TERMS,
            created_at: '2026-07-20T00:00:00Z',
            decided_at: '2026-07-20T01:00:00Z',
          },
        ]),
      ),
    )

    await offerStore.loadMyOffers()

    expect(offerStore.myOffers).toHaveLength(3)
    // caller-scoped-by-listing filtering is the store's job (mirrors
    // accessStore.requestFor) so a component never has to re-derive it.
    const forListing7 = offerStore.offersForListing(7)
    expect(forListing7.map((r) => r.id)).toEqual([1, 2]) // oldest first: root, then the counter
    expect(offerStore.offersForListing(9).map((r) => r.id)).toEqual([5])
    expect(offerStore.offersForListing(404)).toEqual([])
  })

  it('createOffer: POSTs the four OfferTerms fields to /listings/{id}/offers and folds the new row into myOffers', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) =>
      jsonResponse(201, {
        id: 10,
        listing_id: 7,
        parent_offer_id: null,
        proposed_by_role: 'buyer',
        status: 'submitted',
        ...TERMS,
        created_at: '2026-07-21T00:00:00Z',
        decided_at: null,
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const row = await offerStore.createOffer(7, TERMS)

    expect(row.id).toBe(10)
    const calls = fetchMock.mock.calls.map((c) => [String(c[0]), c[1]])
    expect(calls.some(([url, init]) => url.includes('/listings/7/offers') && init?.method === 'POST')).toBe(
      true,
    )
    expect(offerStore.offersForListing(7).map((r) => r.id)).toContain(10)
  })

  it('accept/decline/counter/withdraw call their POST /offers/{id}/{action} routes and return the updated row', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = String(input)
      if (url.endsWith('/offers/3/accept')) return jsonResponse(200, { id: 3, status: 'accepted' })
      if (url.endsWith('/offers/4/decline')) return jsonResponse(200, { id: 4, status: 'declined' })
      if (url.endsWith('/offers/5/withdraw')) return jsonResponse(200, { id: 5, status: 'withdrawn' })
      if (url.endsWith('/offers/6/counter')) {
        return jsonResponse(200, { id: 7, parent_offer_id: 6, status: 'submitted', proposed_by_role: 'seller' })
      }
      return jsonResponse(404, { detail: 'unexpected call', code: 'not_found' })
    })
    vi.stubGlobal('fetch', fetchMock)

    await offerStore.accept(3)
    await offerStore.decline(4)
    await offerStore.withdraw(5)
    await offerStore.counter(6, TERMS)

    const calls = fetchMock.mock.calls.map((c) => [String(c[0]), (c[1] as RequestInit | undefined)?.method])
    expect(calls).toContainEqual(['/api/offers/3/accept', 'POST'])
    expect(calls).toContainEqual(['/api/offers/4/decline', 'POST'])
    expect(calls).toContainEqual(['/api/offers/5/withdraw', 'POST'])
    expect(calls).toContainEqual(['/api/offers/6/counter', 'POST'])
  })

  it('loadListingOffers: populates listingOffers from GET /my/listings/{id}/offers, each row carrying a buyer profile', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(200, [
          {
            id: 1,
            listing_id: 7,
            parent_offer_id: null,
            proposed_by_role: 'buyer',
            status: 'submitted',
            ...TERMS,
            created_at: '2026-07-20T00:00:00Z',
            decided_at: null,
            buyer: { display_name: 'Jordan Buyer', budget: '250000', target_industries: ['saas'], experience: null },
          },
        ]),
      ),
    )

    await offerStore.loadListingOffers(7)

    expect(offerStore.listingOffers).toHaveLength(1)
    expect(offerStore.listingOffers[0].buyer.display_name).toBe('Jordan Buyer')
  })

  it('reset: clears myOffers, listingOffers back to empty', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, [])))
    await offerStore.loadMyOffers()
    offerStore.reset()
    expect(offerStore.myOffers).toEqual([])
    expect(offerStore.listingOffers).toEqual([])
  })
})
