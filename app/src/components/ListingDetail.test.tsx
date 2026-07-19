// M4 — the public listing detail (spec 004 criterion F11).
//
// Added during the branch review: the component shipped citing the backend's
// C1-C4 in its header, but those are response-model criteria with backend
// tests. Nothing exercised this component's own loading / loaded / 404
// rendering — including the part that matters most, that a 404 must not tell
// the visitor whether the listing exists.
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ListingDetail } from './ListingDetail'

const listing = {
  id: 7,
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

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/browse/7']}>
      <Routes>
        <Route path="/browse/:id" element={<ListingDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ListingDetail', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('F11: shows a loading state while the request is in flight', async () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
    renderDetail()
    await waitFor(() => expect(screen.getByLabelText(/loading/i)).toBeInTheDocument())
  })

  it('F11: renders the public listing once loaded, and no identity field', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify(listing), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
      ),
    )
    renderDetail()
    await waitFor(() =>
      expect(screen.getByText(/profitable b2b scheduling saas/i)).toBeInTheDocument(),
    )
    expect(screen.getByText(/locked until the nda is signed/i)).toBeInTheDocument()
    expect(screen.queryByText(/secretco/i)).toBeNull()
  })

  it('F11: a 404 says "not available" and reveals nothing about existence', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: 'Listing not found', code: 'not_found' }), {
            status: 404,
            headers: { 'Content-Type': 'application/json' },
          }),
      ),
    )
    renderDetail()
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/not available/i))
    // The server deliberately cannot distinguish "missing" from "not live"
    // (spec C3). The client must not undo that by narrating a reason.
    const alert = screen.getByRole('alert').textContent ?? ''
    expect(alert).not.toMatch(/draft|pending|review|paused|exist|deleted/i)
  })

  it('F11: sends no Authorization header', async () => {
    localStorage.setItem('token', 'a.b.c')
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify(listing), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderDetail()
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())

    const init = fetchMock.mock.calls[0][1] as RequestInit | undefined
    const headers = (init?.headers ?? {}) as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
    localStorage.clear()
  })
})
