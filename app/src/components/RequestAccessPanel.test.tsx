// M5 — the request-access gate on the listing detail page (spec 005 criteria
// J1, J2, J3, J5, X4).
//
// This is the component that turns `GET /api/listings/{id}/private`'s two
// outcomes (200 vs 403 `nda_access_required`) into the four states plan.md
// names: locked / pending / approved / denied — driven by the gate's response,
// never guessed. J5 is the sharpest edge here: `api.ts` fires the global
// `auth:unauthorized` redirect on 401 only, but a bug that treats "no access"
// the same as "no session" would bounce a perfectly logged-in buyer to
// /login. That must never happen for a 403.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { RequestAccessPanel } from './RequestAccessPanel'
import { authStore } from '../stores/authStore'

const PRIVATE_DATA = {
  company_name: 'Acme Internal Tools LLC',
  website_url: 'https://acme.example.com',
  detailed_financials: 'Full P&L available on request.',
}

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function meBody(ndaSignedAt: string | null) {
  return {
    id: 2,
    email: 'buyer@example.com',
    is_buyer: true,
    is_seller: false,
    is_admin: false,
    display_name: 'Jordan Buyer',
    nda_signed_at: ndaSignedAt,
  }
}

// Sets authStore.user directly (covers an implementation that reads it
// straight off the store) AND stubs `/api/auth/me` (covers an implementation
// that loads it itself, RequireAdmin-style) — the test should not care which.
function stubApi({
  ndaSignedAt = null as string | null,
  privateStatus = 403,
  privateBody = {
    detail: 'You do not have access to this data room.',
    code: 'nda_access_required',
    request_id: 'req_1',
  } as unknown,
} = {}) {
  authStore.user = meBody(ndaSignedAt) as unknown as typeof authStore.user

  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    if (url.includes('/api/auth/me')) {
      return jsonResponse(200, meBody(ndaSignedAt))
    }
    if (url.includes('/api/auth/nda') && method === 'POST') {
      return jsonResponse(200, { nda_signed_at: '2026-07-20T00:00:00Z', nda_version: '1.0' })
    }
    if (url.match(/\/access-request$/) && method === 'POST') {
      return jsonResponse(201, {
        id: 55,
        listing_id: 7,
        status: 'requested',
        created_at: '2026-07-20T00:00:00Z',
      })
    }
    if (url.match(/\/listings\/\d+\/private$/) && method === 'GET') {
      return jsonResponse(privateStatus, privateBody)
    }
    return jsonResponse(404, { detail: 'unexpected call in test', code: 'not_found' })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderPanel() {
  return render(
    <MemoryRouter>
      <RequestAccessPanel listingId={7} />
    </MemoryRouter>,
  )
}

describe('RequestAccessPanel', () => {
  beforeEach(() => {
    authStore.logout()
    localStorage.setItem('token', 'a.b.c')
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    authStore.logout()
  })

  it('X4: shows a loading state while access is being checked', async () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
    renderPanel()
    await waitFor(() => expect(screen.getByLabelText(/loading|checking/i)).toBeInTheDocument())
  })

  it('J5/X4: a 403 nda_access_required renders the locked state with a Request access CTA — not an error page — and never fires the global-401 handler', async () => {
    stubApi()
    const onUnauthorized = vi.fn()
    window.addEventListener('auth:unauthorized', onUnauthorized)

    renderPanel()

    const cta = await screen.findByRole('button', { name: /request access/i })
    expect(cta).toBeInTheDocument()
    expect(screen.queryByText(/something went wrong|unexpected error/i)).not.toBeInTheDocument()
    expect(onUnauthorized).not.toHaveBeenCalled()
    // A 403 must never be mistaken for a dead session.
    expect(localStorage.getItem('token')).toBe('a.b.c')

    window.removeEventListener('auth:unauthorized', onUnauthorized)
  })

  it('X4: a non-403 failure renders a distinct error state without the Request access CTA', async () => {
    stubApi({
      privateStatus: 500,
      privateBody: { detail: 'Something went wrong on our end.', request_id: 'req_9' },
    })
    renderPanel()

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /request access/i })).not.toBeInTheDocument()
  })

  it('J1: an unsigned buyer clicking Request access sees the NDA modal; confirming signs + requests in one gesture and lands on pending', async () => {
    const fetchMock = stubApi({ ndaSignedAt: null })
    const user = userEvent.setup({ delay: null })
    renderPanel()

    await user.click(await screen.findByRole('button', { name: /request access/i }))

    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('checkbox'))
    await user.click(within(dialog).getByRole('button', { name: /sign|agree|confirm/i }))

    await waitFor(() => expect(screen.getByText(/pending|awaiting/i)).toBeInTheDocument())
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    const calls = fetchMock.mock.calls.map((c) => String(c[0]))
    expect(calls.some((u) => u.includes('/api/auth/nda'))).toBe(true)
    expect(calls.some((u) => u.match(/\/access-request$/))).toBe(true)
  })

  it('J2: a signed buyer clicking Request access skips the modal entirely and goes straight to pending', async () => {
    const fetchMock = stubApi({ ndaSignedAt: '2026-01-01T00:00:00Z' })
    const user = userEvent.setup({ delay: null })
    renderPanel()

    await user.click(await screen.findByRole('button', { name: /request access/i }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByText(/pending|awaiting/i)).toBeInTheDocument())

    const calls = fetchMock.mock.calls.map((c) => String(c[0]))
    expect(calls.some((u) => u.includes('/api/auth/nda'))).toBe(false)
    expect(calls.some((u) => u.match(/\/access-request$/))).toBe(true)
  })

  it('J3: an approved buyer sees the private section rendered with real data instead of the gate', async () => {
    stubApi({ privateStatus: 200, privateBody: PRIVATE_DATA })
    renderPanel()

    await waitFor(() => expect(screen.getByText(PRIVATE_DATA.company_name)).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /request access/i })).not.toBeInTheDocument()
  })
})
