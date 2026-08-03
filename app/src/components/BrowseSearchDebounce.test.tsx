// M13 — spec 013 criterion F7: the marketplace search debounce must not
// outlive the component.
//
// `BrowseListings` debounces its search box by 250ms and then writes `q` to the
// query string. `setParams` NAVIGATES, so a timer that survives unmount steers
// a visitor who has already left — specifically, one who opened a listing
// within 250ms of typing gets thrown back to the marketplace.
//
// Its own sibling proves the author knew the pattern: the fetch effect in the
// same component guards the identical hazard with a `cancelled` flag. Only the
// timer was missed.
//
// A separate file rather than an addition to BrowseListings.test.tsx: the spec
// coverage checker attributes a test file to a milestone by the tag in its
// first six lines, so a criterion added to the M4 file would count for spec 004.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
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

// The assertion surface. Reading the router's own location is what makes this
// test about navigation rather than about which component happens to render.
function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname + location.search}</div>
}

describe('BrowseListings — the search debounce (spec 013)', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('F7: a pending search does not navigate after the visitor has opened a listing', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn(async () => page([item])))

    render(
      <MemoryRouter initialEntries={['/browse']}>
        <Routes>
          <Route path="/browse" element={<BrowseListings />} />
          <Route path="/browse/:id" element={<div>Detail page</div>} />
        </Routes>
        <LocationProbe />
      </MemoryRouter>,
    )

    // A result must be on screen BEFORE typing — the race needs something the
    // visitor can click while a newer search is still settling. That is also
    // why it is reachable by hand and not only by a fast test runner.
    await screen.findByText(/profitable b2b scheduling saas/i)

    await user.type(screen.getByLabelText('Search'), 'clinics')

    // Leave immediately, inside the 250ms debounce window.
    const card = screen.getAllByRole('link').find((a) => a.getAttribute('href') === '/browse/1')
    await user.click(card as HTMLElement)
    expect(await screen.findByText('Detail page')).toBeInTheDocument()

    // Give the debounce every chance to fire from the unmounted component.
    await new Promise((resolve) => setTimeout(resolve, 400))

    // Still where the visitor put themselves. Without the cleanup this reads
    // as the marketplace again, with the half-typed search applied.
    expect(screen.getByTestId('location')).toHaveTextContent('/browse/1')
    expect(screen.getByText('Detail page')).toBeInTheDocument()
  })
})
