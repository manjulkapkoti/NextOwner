// M7 — OfferThread: one negotiation's full chain, root -> counters ->
// terminal decision (spec 007 criteria J4, J5; the shared rendering engine
// J3's seller queue and OfferForm's buyer panel both sit on top of).
//
// Each row is expected to render inside a container keyed
// `data-testid="offer-row-{id}"` (mirrors ChatWindow's `message-mine` /
// `message-theirs` convention of giving the test a stable per-item hook
// instead of relying on brittle DOM order alone).
//
// **The security-shaped assertion this file exists for**: decision rights
// (accept/decline/counter) and withdraw rights are strict, disjoint
// opposites for the *same* row (spec 007 D1/D4/S8) — whoever proposed a row's
// terms may only withdraw it; the other party may only decide it. Getting
// this backwards on the frontend wouldn't be caught by the backend's own
// tests (those prove the *server* refuses the wrong caller with 403) but
// would render a button that always 403s, which is exactly the kind of
// "offering a button the server would reject" `AccessRequestQueue.tsx`'s own
// comment already warns against.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { OfferThread } from './OfferThread'
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

describe('OfferThread', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'a.b.c')
    offerStore.reset()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
    offerStore.reset()
  })

  it('renders the full chain in chronological order, root then counter', () => {
    const rows = [
      offerRow({ id: 1, status: 'countered', proposed_by_role: 'buyer', created_at: '2026-07-20T00:00:00Z' }),
      offerRow({
        id: 2,
        parent_offer_id: 1,
        status: 'submitted',
        proposed_by_role: 'seller',
        created_at: '2026-07-20T01:00:00Z',
      }),
    ]
    render(<OfferThread rows={rows} viewerRole="buyer" />)

    const rendered = screen.getAllByTestId(/^offer-row-/)
    expect(rendered.map((el) => el.getAttribute('data-testid'))).toEqual(['offer-row-1', 'offer-row-2'])
  })

  it('J4: accept/decline/counter actions render on the counter row (seller-proposed, submitted) and not on the original, now-terminal offer', () => {
    const rows = [
      offerRow({ id: 1, status: 'countered', proposed_by_role: 'buyer', created_at: '2026-07-20T00:00:00Z' }),
      offerRow({
        id: 2,
        parent_offer_id: 1,
        status: 'submitted',
        proposed_by_role: 'seller',
        created_at: '2026-07-20T01:00:00Z',
      }),
    ]
    render(<OfferThread rows={rows} viewerRole="buyer" />)

    const originalRow = screen.getByTestId('offer-row-1')
    expect(within(originalRow).queryByRole('button', { name: /accept|decline|counter|withdraw/i })).not.toBeInTheDocument()

    const counterRow = screen.getByTestId('offer-row-2')
    expect(within(counterRow).getByRole('button', { name: /accept/i })).toBeInTheDocument()
    expect(within(counterRow).getByRole('button', { name: /decline/i })).toBeInTheDocument()
    expect(within(counterRow).getByRole('button', { name: /counter/i })).toBeInTheDocument()
  })

  it('decision rights and withdraw rights are strict, disjoint opposites for the same row (mirrors D1/D4/S8): the proposer sees only Withdraw', () => {
    const rows = [offerRow({ id: 1, status: 'submitted', proposed_by_role: 'buyer' })]
    render(<OfferThread rows={rows} viewerRole="buyer" />)

    const row = screen.getByTestId('offer-row-1')
    expect(within(row).getByRole('button', { name: /withdraw/i })).toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: /accept|decline|^counter$/i })).not.toBeInTheDocument()
  })

  it('...and the counterparty on that same row sees only Accept/Decline/Counter, never Withdraw', () => {
    const rows = [offerRow({ id: 1, status: 'submitted', proposed_by_role: 'buyer' })]
    render(<OfferThread rows={rows} viewerRole="seller" />)

    const row = screen.getByTestId('offer-row-1')
    expect(within(row).getByRole('button', { name: /accept/i })).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: /decline/i })).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: /^counter$/i })).toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: /withdraw/i })).not.toBeInTheDocument()
  })

  it('a fully terminal chain (e.g. declined) renders no action buttons on any row', () => {
    const rows = [offerRow({ id: 1, status: 'declined', decided_at: '2026-07-20T01:00:00Z' })]
    render(<OfferThread rows={rows} viewerRole="seller" />)

    expect(screen.queryByRole('button', { name: /accept|decline|counter|withdraw/i })).not.toBeInTheDocument()
  })

  it('J5: a decision action that 409s (someone else already acted, or the listing left live) surfaces a generic toast and signals the view to refetch — no crash, no silent no-op', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = String(input)
      if (url.endsWith('/offers/1/accept')) {
        return jsonResponse(409, {
          detail: 'This offer has already been decided.',
          code: 'offer_already_decided',
          request_id: 'req_1',
        })
      }
      return jsonResponse(404, { detail: 'unexpected call in test', code: 'not_found' })
    })
    vi.stubGlobal('fetch', fetchMock)
    const onChange = vi.fn()
    const user = userEvent.setup({ delay: null })

    const rows = [offerRow({ id: 1, status: 'submitted', proposed_by_role: 'buyer' })]
    render(<OfferThread rows={rows} viewerRole="seller" onChange={onChange} />)

    await user.click(screen.getByRole('button', { name: /accept/i }))

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    // The generic contract, not the raw detail leaking implementation — but the
    // component must not swallow the failure silently: it still tells its
    // parent to refetch so a stale "submitted" row is never left on screen.
    await waitFor(() => expect(onChange).toHaveBeenCalled())
    // No crash: the row (and its button) are still present, not blown away.
    expect(screen.getByTestId('offer-row-1')).toBeInTheDocument()
  })

  it('renders an empty chain without crashing', () => {
    render(<OfferThread rows={[]} viewerRole="buyer" />)
    expect(screen.queryByTestId(/^offer-row-/)).not.toBeInTheDocument()
  })
})
