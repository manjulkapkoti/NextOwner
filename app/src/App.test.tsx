// App shell routing + auth integration (spec pre-003 acceptance criteria
// AS1-AS4, AS6). Replaces the M0 health-page test — the DB/API round trip is
// now proven by the M1/M2 backend tests; this proves the shell wires the
// already-built components into a navigable app.
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppShell } from './App'
import { authStore } from './stores/authStore'

function stubEmptyListings() {
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () =>
        new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    ),
  )
}

function renderShellAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppShell />
    </MemoryRouter>,
  )
}

describe('AppShell routing', () => {
  beforeEach(() => authStore.logout())
  afterEach(() => vi.unstubAllGlobals())

  it('AS1: a logged-out visitor hitting /sell sees the login page', async () => {
    renderShellAt('/sell')
    await waitFor(() => expect(screen.getByLabelText(/email/i)).toBeInTheDocument())
  })

  it('AS2: a logged-out visitor hitting /my-listings sees the login page', async () => {
    renderShellAt('/my-listings')
    await waitFor(() => expect(screen.getByLabelText(/email/i)).toBeInTheDocument())
  })

  it('AS3: an already-authed visitor hitting /login is redirected to the dashboard', async () => {
    authStore.setToken('a.b.c')
    stubEmptyListings()
    renderShellAt('/login')
    await waitFor(() => expect(screen.getByText(/no listings yet/i)).toBeInTheDocument())
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
  })

  it('AS4: an auth:unauthorized event clears the session and returns to login', async () => {
    authStore.setToken('a.b.c')
    stubEmptyListings()
    renderShellAt('/my-listings')
    await waitFor(() => expect(screen.getByText(/no listings yet/i)).toBeInTheDocument())

    window.dispatchEvent(new Event('auth:unauthorized'))

    await waitFor(() => expect(screen.getByLabelText(/email/i)).toBeInTheDocument())
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('AS6: an authed visitor hitting the landing page sees their dashboard', async () => {
    authStore.setToken('a.b.c')
    stubEmptyListings()
    renderShellAt('/')
    await waitFor(() => expect(screen.getByText(/no listings yet/i)).toBeInTheDocument())
  })

  it('AS7: a logged-out visitor hitting the landing page sees public content, not the login form', async () => {
    // "NextOwner" alone would also match the nav bar brand — assert on the
    // page's own tagline instead, which is unique to the landing content.
    renderShellAt('/')
    await waitFor(() =>
      expect(screen.getByText(/buying and selling small online businesses/i)).toBeInTheDocument(),
    )
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /log in/i })).toBeInTheDocument()
  })

  it('AS8: a logged-out visitor hitting /register sees the registration form', async () => {
    renderShellAt('/register')
    await waitFor(() => expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument())
  })

  it('AS9: an already-authed visitor hitting /register is redirected to the dashboard', async () => {
    authStore.setToken('a.b.c')
    stubEmptyListings()
    renderShellAt('/register')
    await waitFor(() => expect(screen.getByText(/no listings yet/i)).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /create account/i })).not.toBeInTheDocument()
  })
})
