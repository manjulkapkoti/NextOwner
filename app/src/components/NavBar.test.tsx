// Nav bar logout control (spec pre-003 acceptance criterion AS5).
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { NavBar } from './NavBar'
import { authStore } from '../stores/authStore'

describe('NavBar', () => {
  beforeEach(() => authStore.logout())

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
})
