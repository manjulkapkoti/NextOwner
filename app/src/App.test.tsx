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
    // Tagline updated at M4 with the succession-voice rewrite (spec 004 F7);
    // the criterion is unchanged, only the string it looks for.
    renderShellAt('/')
    await waitFor(() =>
      expect(screen.getByText(/you choose who carries it forward/i)).toBeInTheDocument(),
    )
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /log in/i })).toBeInTheDocument()
  })

  // M4 (spec 004 criterion F7) — the seller-led succession framing leaves the
  // buyer cold unless the page answers "what is in this for me", so the
  // counter-story is a criterion of its own rather than a nice-to-have.
  it('F7: the landing page carries the buyer counter-story alongside the seller story', async () => {
    renderShellAt('/')
    await waitFor(() =>
      expect(screen.getByText(/instead of starting from zero/i)).toBeInTheDocument(),
    )
  })

  // M4 (spec 004 criterion F8) — browse is reachable from the nav whether or
  // not the visitor is signed in. The label stays literal: the brand voice
  // lives in headlines and prose, never in navigation (fold-in constraint).
  it('F8: the nav offers a Browse link to the public marketplace', async () => {
    renderShellAt('/')
    await waitFor(() =>
      expect(screen.getByRole('link', { name: /browse/i })).toHaveAttribute('href', '/browse'),
    )
  })

  // M4 (spec 004 criterion F9) — /browse is public, not a RequireAuth route.
  it('F9: a logged-out visitor hitting /browse sees the marketplace, not the login form', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ items: [], total: 0, limit: 20, offset: 0 }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
      ),
    )
    renderShellAt('/browse')
    await waitFor(() => expect(screen.getByText(/no listings match/i)).toBeInTheDocument())
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
  })

  // The landing page's only actions are the nav's two: Log in for returning
  // visitors, Get started for new ones. The hero deliberately carries no CTA
  // of its own, so there is one of each rather than duplicates.
  it('offers exactly one Log in and one Get started on the landing page', async () => {
    renderShellAt('/')
    await waitFor(() =>
      expect(screen.getByText(/you choose who carries it forward/i)).toBeInTheDocument(),
    )
    expect(screen.getByRole('link', { name: /get started/i })).toHaveAttribute('href', '/register')
    expect(screen.getAllByRole('link', { name: /log in/i })).toHaveLength(1)
  })

  // Signup is a dedicated page: it brings its own header, so the app nav (and
  // its competing wordmark and exits) must not render there.
  it('hides the app nav on the signup page', async () => {
    renderShellAt('/register')
    await waitFor(() => expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument())
    expect(screen.queryByRole('link', { name: /get started/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /back/i })).toBeInTheDocument()
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
