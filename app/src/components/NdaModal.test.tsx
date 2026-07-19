// M5 — the click-wrap platform NDA modal (spec 005 criterion J1).
//
// Signing the platform NDA and creating the access request are two API calls
// (`POST /api/auth/nda` then `POST /api/listings/{id}/access-request`) but
// must read as ONE user action: the buyer checks the box, clicks once, and
// both calls go out before the modal reports success. Splitting them across
// two gestures would let a buyer "half-sign" — an access request created
// without ever agreeing to the NDA text, which is exactly what
// `require_signed_nda` (B2) exists to prevent. The sign call must land before
// the request call, or the request would 403 `nda_not_signed` against a real
// server.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { NdaModal } from './NdaModal'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function stubApi() {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    if (url.includes('/api/auth/nda') && method === 'POST') {
      return jsonResponse(200, { nda_signed_at: '2026-07-20T00:00:00Z', nda_version: '1.0' })
    }
    if (url.includes('/access-request') && method === 'POST') {
      return jsonResponse(201, {
        id: 55,
        listing_id: 7,
        status: 'requested',
        created_at: '2026-07-20T00:00:00Z',
      })
    }
    return jsonResponse(404, { detail: 'unexpected call in test', code: 'not_found' })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('NdaModal', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('J1: renders the NDA agreement with a checkbox and a confirm button disabled until agreed', () => {
    stubApi()
    render(<NdaModal open listingId={7} onClose={() => {}} onSigned={() => {}} />)

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText(/nda|non-disclosure/i)).toBeInTheDocument()

    const checkbox = screen.getByRole('checkbox')
    const confirm = screen.getByRole('button', { name: /sign|agree|confirm/i })
    expect(checkbox).not.toBeChecked()
    expect(confirm).toBeDisabled()
  })

  it('renders nothing when closed', () => {
    stubApi()
    render(<NdaModal open={false} listingId={7} onClose={() => {}} onSigned={() => {}} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('J1: confirming signs the NDA and creates the access request in one gesture (two API calls)', async () => {
    const fetchMock = stubApi()
    const onSigned = vi.fn()
    const user = userEvent.setup({ delay: null })
    render(<NdaModal open listingId={7} onClose={() => {}} onSigned={onSigned} />)

    await user.click(screen.getByRole('checkbox'))
    const confirm = screen.getByRole('button', { name: /sign|agree|confirm/i })
    expect(confirm).toBeEnabled()

    // ONE click …
    await user.click(confirm)

    // … but two API calls, sign strictly before request.
    await waitFor(() => expect(onSigned).toHaveBeenCalled())
    const calls = fetchMock.mock.calls.map((c) => String(c[0]))
    const ndaCallIndex = calls.findIndex((u) => u.includes('/api/auth/nda'))
    const requestCallIndex = calls.findIndex((u) => u.includes('/access-request'))
    expect(ndaCallIndex).toBeGreaterThanOrEqual(0)
    expect(requestCallIndex).toBeGreaterThanOrEqual(0)
    expect(ndaCallIndex).toBeLessThan(requestCallIndex)
  })

  it('cancelling closes the modal without signing or requesting anything', async () => {
    const fetchMock = stubApi()
    const onClose = vi.fn()
    const user = userEvent.setup({ delay: null })
    render(<NdaModal open listingId={7} onClose={onClose} onSigned={() => {}} />)

    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(onClose).toHaveBeenCalled()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
