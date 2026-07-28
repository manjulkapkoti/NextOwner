// Nav bar logout control (spec pre-003 acceptance criterion AS5) + the M6
// "Messages" unread badge (spec 006 J1).
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { NavBar } from './NavBar'
import { authStore } from '../stores/authStore'
import { chatStore } from '../stores/chatStore'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('NavBar', () => {
  beforeEach(() => authStore.logout())
  afterEach(() => {
    vi.unstubAllGlobals()
    chatStore.reset()
  })

  // UI Pass 2 moved Logout from an always-visible inline button into the
  // account (avatar) menu, so the accessible path is now "open the account
  // menu, then click Logout" rather than a bare button — the assertion below
  // (session cleared, redirected to /login) is unchanged.
  it('AS5: clicking Logout in the account menu clears the session and returns to /login', async () => {
    authStore.setToken('a.b.c')
    render(
      <MemoryRouter initialEntries={['/my-listings']}>
        <Routes>
          <Route path="/login" element={<div>Login page</div>} />
          <Route path="/my-listings" element={<NavBar />} />
        </Routes>
      </MemoryRouter>,
    )

    await userEvent.click(screen.getByRole('button', { name: /account menu/i }))
    const logoutItem = screen.getByRole('menuitem', { name: /logout/i })
    expect(logoutItem).toBeInTheDocument()

    await userEvent.click(logoutItem)

    expect(screen.getByText('Login page')).toBeInTheDocument()
    expect(localStorage.getItem('token')).toBeNull()
  })

  // Both logged-out actions live top-right on every page, so a visitor always
  // finds them in the same place: Log in for returning users, Get started for
  // new ones.
  it('offers a logged-out visitor Log in and Get started', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <NavBar />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: /log in/i })).toHaveAttribute('href', '/login')
    expect(screen.getByRole('link', { name: /get started/i })).toHaveAttribute('href', '/register')
    // Authed-only actions must not leak to anonymous visitors.
    expect(screen.queryByRole('button', { name: /logout/i })).not.toBeInTheDocument()
  })

  // UI Pass 2 — Logout now lives behind two closed menus (the desktop account
  // menu, the mobile hamburger), neither of which renders its items while
  // closed, so "Logout" is never ambiguous in the DOM: it does not exist at
  // all until one of the two triggers is opened.
  it('renders no bare Logout control until a menu is opened', () => {
    authStore.setToken('a.b.c')
    render(
      <MemoryRouter initialEntries={['/my-listings']}>
        <NavBar />
      </MemoryRouter>,
    )

    expect(screen.queryByRole('button', { name: /^logout$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /logout/i })).not.toBeInTheDocument()
  })

  // Below `sm` every authed action (not just the 4 kept inline on desktop)
  // collapses behind the one hamburger control — the mobile menu is the full
  // set, not a subset (the audit's finding: Notifications/Saved searches were
  // previously missing here).
  it('collapses every authed action into the mobile hamburger menu', async () => {
    authStore.setToken('a.b.c')
    render(
      <MemoryRouter initialEntries={['/my-listings']}>
        <NavBar />
      </MemoryRouter>,
    )

    await userEvent.click(screen.getByRole('button', { name: /open menu/i }))
    expect(screen.getByRole('menuitem', { name: /list a business/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /my listings/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /my offers/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /watchlist/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /saved searches/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /notifications/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /messages/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /logout/i })).toBeInTheDocument()
  })

  // The desktop account menu (the avatar button) carries the same
  // destinations that used to be bare inline buttons — Watchlist and Saved
  // searches are new nav surface area entirely (previously URL-only).
  it('opens Watchlist, Saved searches and Logout from the account menu', async () => {
    authStore.setToken('a.b.c')
    render(
      <MemoryRouter initialEntries={['/my-listings']}>
        <NavBar />
      </MemoryRouter>,
    )

    await userEvent.click(screen.getByRole('button', { name: /account menu/i }))
    expect(screen.getByRole('menuitem', { name: /watchlist/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /saved searches/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /logout/i })).toBeInTheDocument()
  })

  it('gives every icon-only nav control an accessible name', () => {
    authStore.setToken('a.b.c')
    render(
      <MemoryRouter initialEntries={['/my-listings']}>
        <NavBar />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: /^notifications$/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /^messages$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^account menu$/i })).toBeInTheDocument()
  })

  it('J1: a signed-in user with unread messages sees a Messages link with the total unread count', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(200, [
          { id: 1, listing_id: 7, listing_headline: 'A', counterpart_display_name: 'X', unread_count: 2, last_message_at: null },
          { id: 2, listing_id: 8, listing_headline: 'B', counterpart_display_name: 'Y', unread_count: 1, last_message_at: null },
        ]),
      ),
    )
    authStore.setToken('a.b.c')
    render(
      <MemoryRouter initialEntries={['/my-listings']}>
        <NavBar />
      </MemoryRouter>,
    )

    const link = await screen.findByRole('link', { name: /messages/i })
    await waitFor(() => expect(within(link).getByText('3')).toBeInTheDocument())
  })

  // M10 — buyer verification (spec 010, D4: no role gate). The link belongs
  // beside Watchlist/Saved searches in both menus, for any authenticated user.
  it('M10: offers Verification from both the account menu and the mobile menu', async () => {
    authStore.setToken('a.b.c')
    render(
      <MemoryRouter initialEntries={['/my-listings']}>
        <NavBar />
      </MemoryRouter>,
    )

    await userEvent.click(screen.getByRole('button', { name: /account menu/i }))
    expect(screen.getByRole('menuitem', { name: /^verification$/i })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('menuitem', { name: /^verification$/i }))

    await userEvent.click(screen.getByRole('button', { name: /open menu/i }))
    expect(screen.getByRole('menuitem', { name: /^verification$/i })).toBeInTheDocument()
  })

  // M10 — the admin section ("Curation queue" / "Verifications") is hidden
  // from an ordinary authenticated user entirely, not just unreachable.
  it('M10: hides the admin section from a non-admin', async () => {
    // Stubbed so the mount-time chatStore/notificationStore refresh (spec 006
    // J1) resolves cleanly instead of hitting an un-mocked network call.
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, [])))
    authStore.setToken('a.b.c')
    authStore.user = {
      id: 1,
      email: 'buyer@example.com',
      is_buyer: true,
      is_seller: false,
      is_admin: false,
      display_name: null,
    } as unknown as typeof authStore.user
    render(
      <MemoryRouter initialEntries={['/my-listings']}>
        <NavBar />
      </MemoryRouter>,
    )

    await userEvent.click(screen.getByRole('button', { name: /account menu/i }))
    expect(screen.queryByRole('menuitem', { name: /curation queue/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /^verifications$/i })).not.toBeInTheDocument()
  })

  // M10 — an admin sees both admin destinations, alongside the ordinary
  // buyer-facing "Verification" link (a dual account is not unusual, FR-2).
  it('M10: shows Curation queue and Verifications to an admin', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, [])))
    authStore.setToken('a.b.c')
    authStore.user = {
      id: 1,
      email: 'admin@example.com',
      is_buyer: true,
      is_seller: false,
      is_admin: true,
      display_name: null,
    } as unknown as typeof authStore.user
    render(
      <MemoryRouter initialEntries={['/my-listings']}>
        <NavBar />
      </MemoryRouter>,
    )

    await userEvent.click(screen.getByRole('button', { name: /account menu/i }))
    expect(screen.getByRole('menuitem', { name: /curation queue/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /^verifications$/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /^verification$/i })).toBeInTheDocument()
  })

  // M11 — spec 011 U8. Written failing first: the link does not exist yet.
  //
  // Asserted for a **logged-out** visitor specifically. The calculator is a lead
  // magnet aimed at people who have never signed up, so a link that only appears
  // once you have an account is the one placement that defeats its purpose —
  // and, being inside the account menu, is exactly where it would land by
  // habit.
  //
  // **What this test cannot see, recorded so a green run is not over-read:**
  // jsdom does not evaluate media queries, so a `display: { xs: 'none' }` on
  // this link would leave the test passing while the link was invisible on
  // every phone. That is not hypothetical — it is what the first draft of the
  // component did, and only the M11 docs audit caught it, by reading two files'
  // rationale against each other rather than by running anything. The breakpoint
  // behaviour is covered, if at all, by the Playwright layout job, not here.
  it('U8: the valuation calculator is reachable from the nav when logged out', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <NavBar />
      </MemoryRouter>,
    )

    const link = screen.getByRole('link', { name: /valuation|what.*worth/i })
    expect(link).toHaveAttribute('href', '/valuation')
  })
})
