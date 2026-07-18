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
})
