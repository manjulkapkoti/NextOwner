// M3 — the admin curation queue (spec 003 acceptance criteria F1-F3).
//
// The client gate is UX only. The boundary is the server (spec A3), covered by
// backend/tests/test_curation.py — these prove the admin can do the job and a
// non-admin is not shown a queue to poke at.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppShell } from '../App'
import { authStore } from '../stores/authStore'

const PENDING = [
  {
    id: 7,
    headline: 'Profitable B2B scheduling SaaS',
    type: 'saas',
    asking_price: '500000.00',
    status: 'pending_review',
    created_at: '2026-07-19T10:00:00Z',
    company_name: 'Acme Internal Tools LLC',
    website_url: 'https://acme.example.com',
  },
]

// `me` decides whether the client believes the caller is an admin; the queue
// call returns the rows.
function stubApi({ isAdmin, queue = PENDING }: { isAdmin: boolean; queue?: unknown[] }) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const body = url.includes('/api/auth/me')
        ? { id: 1, email: 'admin@example.com', is_admin: isAdmin, is_buyer: true, is_seller: false }
        : queue
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }),
  )
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppShell />
    </MemoryRouter>,
  )
}

describe('AdminQueue', () => {
  beforeEach(() => {
    authStore.logout()
    localStorage.setItem('token', 'a.b.c')
  })
  afterEach(() => vi.unstubAllGlobals())

  it('F1: an admin sees the pending listings with headline, price and status', async () => {
    stubApi({ isAdmin: true })
    renderAt('/admin')

    await waitFor(() =>
      expect(screen.getByText('Profitable B2B scheduling SaaS')).toBeInTheDocument(),
    )
    expect(screen.getByText(/500,?000/)).toBeInTheDocument()
    expect(screen.getByText(/in review/i)).toBeInTheDocument()
  })

  it('F2: a non-admin is redirected away and sees no queue', async () => {
    stubApi({ isAdmin: false, queue: [] })
    renderAt('/admin')

    // Asserted positively: they must land somewhere real. Checking only that
    // the queue is absent would pass vacuously while /admin does not exist —
    // a test that cannot fail proves nothing.
    await waitFor(() => expect(screen.getByText(/your listings/i)).toBeInTheDocument())
    expect(screen.queryByText('Profitable B2B scheduling SaaS')).not.toBeInTheDocument()
  })

  it('F3: rejecting without a reason is blocked inline, not sent to the server', async () => {
    stubApi({ isAdmin: true })
    const user = userEvent.setup({ delay: null })
    renderAt('/admin')

    await waitFor(() =>
      expect(screen.getByText('Profitable B2B scheduling SaaS')).toBeInTheDocument(),
    )
    await user.click(screen.getByRole('button', { name: /reject/i }))
    // The dialog's own confirm, with the reason left empty.
    await user.click(screen.getByRole('button', { name: /confirm reject/i }))

    expect(await screen.findByText(/reason is required/i)).toBeInTheDocument()
    const calls = (fetch as unknown as { mock: { calls: string[][] } }).mock.calls
    expect(calls.some((c) => String(c[0]).includes('/reject'))).toBe(false)
  })
})
