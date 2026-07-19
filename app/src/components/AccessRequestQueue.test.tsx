// M5 — the seller's per-listing access-request queue (spec 005 criterion J4;
// FR-14; `GET /api/my/listings/{id}/access-requests`, D7).
//
// D5 (owner-approved 2026-07-20): M5 ships the buyer's profile half of FR-14
// only — no verification badge. That field is M10's to add, so it is
// deliberately absent from the mock row below and this file makes no
// assertion about one either way, positive or negative.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AccessRequestQueue } from './AccessRequestQueue'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const BUYER = {
  display_name: 'Jordan Buyer',
  budget: '250000.00',
  target_industries: ['saas', 'ecommerce'],
  experience: 'Former operator of two SaaS exits.',
}

function stubQueue(initialStatus: 'requested' | 'approved' | 'denied') {
  let status: string = initialStatus
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    if (url.includes('/approve') && method === 'POST') {
      status = 'approved'
      return jsonResponse(200, { id: 11, status })
    }
    if (url.includes('/deny') && method === 'POST') {
      status = 'denied'
      return jsonResponse(200, { id: 11, status })
    }
    if (url.includes('/revoke') && method === 'POST') {
      status = 'revoked'
      return jsonResponse(200, { id: 11, status })
    }
    if (url.match(/\/my\/listings\/\d+\/access-requests$/) && method === 'GET') {
      return jsonResponse(200, [
        {
          id: 11,
          listing_id: 7,
          status,
          created_at: '2026-07-19T10:00:00Z',
          decided_at: status === 'requested' ? null : '2026-07-19T11:00:00Z',
          buyer: BUYER,
        },
      ])
    }
    return jsonResponse(404, { detail: 'unexpected call in test', code: 'not_found' })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('AccessRequestQueue', () => {
  beforeEach(() => localStorage.setItem('token', 'a.b.c'))
  afterEach(() => vi.unstubAllGlobals())

  it('J4: shows the buyer profile with approve/deny actions on a requested row', async () => {
    stubQueue('requested')
    render(<AccessRequestQueue listingId={7} />)

    await waitFor(() => expect(screen.getByText('Jordan Buyer')).toBeInTheDocument())
    expect(screen.getByText(/250,?000/)).toBeInTheDocument()
    expect(screen.getByText(/saas/i)).toBeInTheDocument()
    expect(screen.getByText(/former operator of two saas exits/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /deny/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /revoke/i })).not.toBeInTheDocument()
  })

  it('J4: an approved row offers Revoke instead of Approve/Deny', async () => {
    stubQueue('approved')
    render(<AccessRequestQueue listingId={7} />)

    await waitFor(() => expect(screen.getByText('Jordan Buyer')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /revoke/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^approve$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^deny$/i })).not.toBeInTheDocument()
  })

  it('J4: approving a request calls the approve endpoint and the row reflects the decision', async () => {
    const fetchMock = stubQueue('requested')
    const user = userEvent.setup({ delay: null })
    render(<AccessRequestQueue listingId={7} />)

    await waitFor(() => expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /approve/i }))

    await waitFor(() => expect(screen.getByRole('button', { name: /revoke/i })).toBeInTheDocument())
    const calls = fetchMock.mock.calls.map((c) => String(c[0]))
    expect(calls.some((u) => u.includes('/access-requests/11/approve'))).toBe(true)
  })

  it('J4: revoking an approved request calls the revoke endpoint', async () => {
    const fetchMock = stubQueue('approved')
    const user = userEvent.setup({ delay: null })
    render(<AccessRequestQueue listingId={7} />)

    await waitFor(() => expect(screen.getByRole('button', { name: /revoke/i })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /revoke/i }))

    await waitFor(() => {
      const calls = fetchMock.mock.calls.map((c) => String(c[0]))
      expect(calls.some((u) => u.includes('/access-requests/11/revoke'))).toBe(true)
    })
  })
})
