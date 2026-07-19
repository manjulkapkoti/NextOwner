// M4 — the marketplace grid (spec 004 criteria F2-F6, E-4).
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BrowseListings } from './BrowseListings'

const item = {
  id: 1,
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

function page(items: unknown[], total = items.length) {
  return new Response(JSON.stringify({ items, total, limit: 20, offset: 0 }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderBrowse() {
  return render(
    <MemoryRouter>
      <BrowseListings />
    </MemoryRouter>,
  )
}

describe('BrowseListings', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => vi.unstubAllGlobals())

  it('F2: renders a card per item returned by the API', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => page([item])))
    renderBrowse()
    await waitFor(() =>
      expect(screen.getByText(/profitable b2b scheduling saas/i)).toBeInTheDocument(),
    )
  })

  it('F3: shows a loading state while the request is in flight', async () => {
    // A promise that never settles — the component must show progress, not a
    // blank page, while it waits.
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
    renderBrowse()
    await waitFor(() => expect(screen.getByLabelText(/loading/i)).toBeInTheDocument())
  })

  it('F4: shows an empty state when nothing matches', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => page([], 0)))
    renderBrowse()
    await waitFor(() => expect(screen.getByText(/no listings match/i)).toBeInTheDocument())
  })

  it('F5: shows an error state when the request fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('{"detail":"boom"}', { status: 500 })),
    )
    renderBrowse()
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })

  it('F6: changing a filter refetches with the filter in the query string', async () => {
    // Typed as `fetch`, not `vi.fn(async () => ...)` — a zero-arg mock gives
    // `mock.calls` an empty-tuple element type, so indexing it fails `tsc -b`.
    const fetchMock = vi.fn<typeof fetch>(async () => page([item]))
    vi.stubGlobal('fetch', fetchMock)
    renderBrowse()
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())

    await userEvent.type(screen.getByLabelText(/search/i), 'clinics')

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]))
      expect(urls.some((url) => url.includes('q=clinics'))).toBe(true)
    })
  })

  it('S11: browsing sends no Authorization header', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => page([item]))
    vi.stubGlobal('fetch', fetchMock)
    renderBrowse()
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())

    const init = fetchMock.mock.calls[0][1] as RequestInit | undefined
    const headers = (init?.headers ?? {}) as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
  })

  it('E-4: surfaces a 422 as a readable message, not a raw error object', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: 'min_price must be a number', code: 'validation_error' }), {
            status: 422,
            headers: { 'Content-Type': 'application/json' },
          }),
      ),
    )
    renderBrowse()
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/min_price/i))
    expect(screen.queryByText(/\[object Object\]/)).toBeNull()
  })
})
