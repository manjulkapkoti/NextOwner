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

  it('AS5: shows Logout when authed; clicking it clears the session and returns to /login', async () => {
    authStore.setToken('a.b.c')
    render(
      <MemoryRouter initialEntries={['/my-listings']}>
        <Routes>
          <Route path="/login" element={<div>Login page</div>} />
          <Route path="/my-listings" element={<NavBar />} />
        </Routes>
      </MemoryRouter>,
    )

    const logoutButton = screen.getByRole('button', { name: /logout/i })
    expect(logoutButton).toBeInTheDocument()

    await userEvent.click(logoutButton)

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

  // Below `sm` the three authed actions collapse behind one control; the menu
  // renders nothing while closed, so "Logout" is never ambiguous in the DOM.
  it('collapses the authed actions into a menu control on narrow widths', async () => {
    authStore.setToken('a.b.c')
    render(
      <MemoryRouter initialEntries={['/my-listings']}>
        <NavBar />
      </MemoryRouter>,
    )

    expect(screen.getAllByRole('button', { name: /logout/i })).toHaveLength(1)

    await userEvent.click(screen.getByRole('button', { name: /open menu/i }))
    expect(screen.getByRole('menuitem', { name: /list a business/i })).toBeInTheDocument()
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
})
