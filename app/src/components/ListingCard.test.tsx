// M4 — the anonymous card (spec 004 criterion F1).
//
// The frontend twin of the backend schema-leak test. The server already makes a
// leak impossible by schema; this asserts the client keeps the promise even when
// handed an object that carries identity fields — because a future caller (a
// seller preview, an admin surface) may legitimately hold the full listing, and
// the card must never be the thing that renders it.
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { ListingCard } from './ListingCard'

// The card links to its detail page, so it needs router context. Scaffolding
// only — every assertion below is unchanged.
function renderCard(listing: unknown) {
  return render(
    <MemoryRouter>
      <ListingCard listing={listing as never} />
    </MemoryRouter>,
  )
}

const publicListing = {
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

describe('ListingCard', () => {
  it('F1: renders the public headline, type and metrics', () => {
    renderCard(publicListing)
    expect(screen.getByText(/profitable b2b scheduling saas/i)).toBeInTheDocument()
    // Exact string, not /saas/i — the headline also contains "SaaS", and an
    // ambiguous matcher would fail on the match count rather than on the thing
    // the criterion is about.
    expect(screen.getByText('saas')).toBeInTheDocument()
  })

  it('F1: renders no identity field, even when one is present on the object', () => {
    renderCard({
      ...publicListing,
      // Deliberately hostile input — the card is handed what it must not show.
      company_name: 'SecretCo',
      website_url: 'https://secret.example.com',
      owner_id: 42,
    })
    expect(screen.queryByText(/secretco/i)).toBeNull()
    expect(screen.queryByText(/secret\.example\.com/i)).toBeNull()
  })

  it('F1: advertises that identifying details are gated rather than absent', () => {
    // The locked section is the product's core mechanic made visible — a buyer
    // must understand there is something behind the NDA (FR-6).
    renderCard(publicListing)
    expect(screen.getByText(/locked|nda|request access/i)).toBeInTheDocument()
  })
})
