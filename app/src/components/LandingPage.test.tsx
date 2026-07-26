// UI Pass 3 Part A — the two new "value cards" (Sellers / Buyers) on the
// landing page. Colour is Part C's job and is asserted nowhere here; this
// only covers structure: both eyebrows render, both CTAs resolve to the
// right destination, and the section sits before the 3-step gate band in DOM
// order.
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import { LandingPage } from './LandingPage'
import { authStore } from '../stores/authStore'

function renderLanding() {
  return render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>,
  )
}

describe('LandingPage — Part A spotlight cards', () => {
  afterEach(() => {
    authStore.logout()
  })

  it('renders both eyebrows (SELLERS, BUYERS)', () => {
    renderLanding()
    expect(screen.getByText('SELLERS')).toBeInTheDocument()
    expect(screen.getByText('BUYERS')).toBeInTheDocument()
  })

  // The hero already has its own "List your business" / "Browse listings"
  // CTAs (Pass 2), so the new spotlight cards' CTAs share the same visible
  // name — the spotlight card's copy is the *second* occurrence in DOM order.
  it('the Sellers CTA resolves to /register when logged out, and to /sell when logged in', () => {
    const { unmount } = renderLanding()
    const loggedOutCta = screen.getAllByRole('link', { name: /list your business/i })[1]
    expect(loggedOutCta).toHaveAttribute('href', '/register')
    unmount()

    authStore.setToken('a.b.c')
    renderLanding()
    const loggedInCta = screen.getAllByRole('link', { name: /list your business/i })[1]
    expect(loggedInCta).toHaveAttribute('href', '/sell')
  })

  it('the Buyers CTA resolves to /browse', () => {
    renderLanding()
    const ctas = screen.getAllByRole('link', { name: /browse listings/i })
    expect(ctas[1]).toHaveAttribute('href', '/browse')
  })

  it('the new section appears before the 3-step gate band in DOM order', () => {
    renderLanding()
    const sellersEyebrow = screen.getByText('SELLERS')
    const gateBandHeading = screen.getByText('Browse anonymously')

    // DOCUMENT_POSITION_FOLLOWING (4): sellersEyebrow comes before gateBandHeading.
    const position = sellersEyebrow.compareDocumentPosition(gateBandHeading)
    expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})
