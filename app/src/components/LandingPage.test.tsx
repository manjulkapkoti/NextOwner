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

  // The hero's own "List your business" / "Browse listings" button pair was
  // removed as a follow-up to Pass 3 (owner feedback: it duplicated the
  // spotlight cards' CTAs with less substance) — the spotlight cards are now
  // the only occurrence of each, so no index disambiguation is needed.
  it('the Sellers CTA resolves to /register when logged out, and to /sell when logged in', () => {
    const { unmount } = renderLanding()
    const loggedOutCta = screen.getByRole('link', { name: /list your business/i })
    expect(loggedOutCta).toHaveAttribute('href', '/register')
    unmount()

    authStore.setToken('a.b.c')
    renderLanding()
    const loggedInCta = screen.getByRole('link', { name: /list your business/i })
    expect(loggedInCta).toHaveAttribute('href', '/sell')
  })

  it('the Buyers CTA resolves to /browse', () => {
    renderLanding()
    const cta = screen.getByRole('link', { name: /browse listings/i })
    expect(cta).toHaveAttribute('href', '/browse')
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
