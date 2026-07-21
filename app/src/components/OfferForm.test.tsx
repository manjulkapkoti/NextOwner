// M7 — the buyer's offer panel on the listing detail page (spec 007 criteria
// J1, J2, X4).
//
// Rendered on the listing detail page only once the buyer already has
// approved private access (the parent decides that, exactly like
// `RequestAccessPanel` decides when to render `PrivateSection` — this test
// mounts `OfferForm` directly, the same "test the gated component in
// isolation" shape `PrivateSection.test.tsx` already uses).
//
// **State source**: fetched on mount from `GET /api/my/offers` via
// `offerStore.loadMyOffers()` + `offerStore.offersForListing(listingId)` —
// never inferred only from a POST response held in local state, for the
// identical reason `RequestAccessPanel`'s J2 test polices at M5: a returning
// buyer must see their real status on reload, not a stale "make an offer"
// button inviting a 409 `offer_already_active` (spec 007 A7/D7).
//
// **X4's eight states** all live here because this component IS "the offer
// panel" X4 names: loading / no-offer-yet / submitted (mine) /
// awaiting-my-decision / accepted / declined / withdrawn / errored. The
// "current" row for a listing is whichever one is still `submitted` (at most
// one, D7) — or, once the chain is fully terminal, the most recently created
// row.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { OfferForm } from './OfferForm'
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

function offerRow(overrides: Record<string, unknown>) {
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

function stubMyOffers(rows: unknown[]) {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    if (url.match(/\/my\/offers$/) && method === 'GET') return jsonResponse(200, rows)
    if (url.match(/\/listings\/\d+\/offers$/) && method === 'POST') {
      return jsonResponse(201, offerRow({ id: 99 }))
    }
    return jsonResponse(404, { detail: 'unexpected call in test', code: 'not_found' })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderForm() {
  return render(<OfferForm listingId={7} />)
}

describe('OfferForm', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'a.b.c')
    offerStore.reset()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
    offerStore.reset()
  })

  it('J1: a buyer with approved access and no active offer sees a Make an offer form with all four OfferTerms fields', async () => {
    stubMyOffers([])
    renderForm()

    await screen.findByRole('button', { name: /make an offer|submit offer/i })
    expect(screen.getByLabelText(/price/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/structure/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/contingenc/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/close date/i)).toBeInTheDocument()
  })

  it('J1: submitting the form posts the four fields and the panel leaves the empty state', async () => {
    const fetchMock = stubMyOffers([])
    const user = userEvent.setup({ delay: null })
    renderForm()

    await user.type(await screen.findByLabelText(/price/i), TERMS.price)
    await user.type(screen.getByLabelText(/structure/i), TERMS.structure)
    await user.type(screen.getByLabelText(/contingenc/i), TERMS.contingencies)
    await user.type(screen.getByLabelText(/close date/i), TERMS.proposed_close_date)
    await user.click(screen.getByRole('button', { name: /make an offer|submit offer/i }))

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /make an offer|submit offer/i })).not.toBeInTheDocument(),
    )
    const calls = fetchMock.mock.calls.map((c) => String(c[0]))
    expect(calls.some((u) => u.match(/\/listings\/7\/offers$/))).toBe(true)
  })

  it('J2: a buyer with an active submitted offer sees it replaced by status — never a duplicate form', async () => {
    stubMyOffers([offerRow({ proposed_by_role: 'buyer', status: 'submitted' })])
    renderForm()

    await waitFor(() => expect(screen.getByText(/seller/i)).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /make an offer|submit offer/i })).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/^price/i)).not.toBeInTheDocument()
  })

  describe('X4: the offer panel renders each state distinctly and never crashes', () => {
    it('X4: loading — a spinner shows while the buyer\'s offer status is being checked', async () => {
      vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
      renderForm()
      await waitFor(() => expect(screen.getByLabelText(/loading|checking/i)).toBeInTheDocument())
    })

    it('X4: no-offer-yet — the create form is shown', async () => {
      stubMyOffers([])
      renderForm()
      expect(await screen.findByRole('button', { name: /make an offer|submit offer/i })).toBeInTheDocument()
    })

    it('X4: submitted (mine) — a buyer-proposed offer awaiting the seller renders a pending state', async () => {
      stubMyOffers([offerRow({ proposed_by_role: 'buyer', status: 'submitted' })])
      renderForm()
      expect(await screen.findByText(/seller/i)).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /accept|decline/i })).not.toBeInTheDocument()
    })

    it('X4: awaiting-my-decision — a seller-proposed counter still submitted surfaces accept/decline/counter to the buyer', async () => {
      stubMyOffers([
        offerRow({ id: 1, status: 'countered', proposed_by_role: 'buyer', created_at: '2026-07-20T00:00:00Z' }),
        offerRow({
          id: 2,
          parent_offer_id: 1,
          status: 'submitted',
          proposed_by_role: 'seller',
          created_at: '2026-07-20T01:00:00Z',
        }),
      ])
      renderForm()

      expect(await screen.findByRole('button', { name: /accept/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /decline/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /counter/i })).toBeInTheDocument()
      // The action belongs on the counter, not the original — D1/J4.
      expect(screen.queryByRole('button', { name: /make an offer|submit offer/i })).not.toBeInTheDocument()
    })

    it('X4: accepted — a terminal accepted offer is shown with no actions', async () => {
      stubMyOffers([offerRow({ status: 'accepted', decided_at: '2026-07-20T02:00:00Z' })])
      renderForm()
      expect(await screen.findByText(/accepted/i)).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /accept|decline|counter|withdraw/i })).not.toBeInTheDocument()
    })

    it('X4: declined — a terminal declined offer is shown with no actions', async () => {
      stubMyOffers([offerRow({ status: 'declined', decided_at: '2026-07-20T02:00:00Z' })])
      renderForm()
      expect(await screen.findByText(/declined/i)).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /accept|decline|counter|withdraw/i })).not.toBeInTheDocument()
    })

    it('X4: withdrawn — a self-withdrawn offer is shown with no actions', async () => {
      stubMyOffers([offerRow({ status: 'withdrawn', decided_at: '2026-07-20T02:00:00Z' })])
      renderForm()
      expect(await screen.findByText(/withdrawn/i)).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /accept|decline|counter|withdraw/i })).not.toBeInTheDocument()
    })

    it('X4: errored — a non-403/401 failure renders a distinct error state, not a crash and not the create form', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () => jsonResponse(500, { detail: 'Something went wrong.', request_id: 'req_1' })),
      )
      renderForm()
      expect(await screen.findByRole('alert')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /make an offer|submit offer/i })).not.toBeInTheDocument()
    })
  })
})
