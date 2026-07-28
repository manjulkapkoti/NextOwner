// M10 — the admin verification queue (spec 010 § Frontend), the demand-side
// sibling of AdminQueue.test.tsx (M3). The client route guard is UX only; the
// boundary is `require_admin` on the server, covered by
// backend/tests/test_verification.py.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppShell } from '../App'
import { authStore } from '../stores/authStore'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const PENDING_ROW = {
  user_id: 42,
  email: 'jordan@example.com',
  display_name: 'Jordan Buyer',
  budget: '250000.00',
  target_industries: 'saas',
  experience: 'Former operator of two SaaS exits.',
  verification_status: 'pending',
  documents: [
    {
      id: 5,
      original_filename: 'bank-statement.pdf',
      content_type: 'application/pdf',
      size_bytes: 2048,
      uploaded_at: '2026-07-20T00:00:00Z',
    },
  ],
}

const VERIFIED_ROW = {
  ...PENDING_ROW,
  user_id: 43,
  display_name: 'Alex Verified',
  verification_status: 'verified',
}

function stubApi({
  isAdmin,
  byStatus = { pending: [PENDING_ROW], verified: [], rejected: [] },
}: {
  isAdmin: boolean
  byStatus?: Record<string, unknown[]>
}) {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input)
    const method = init?.method ?? 'GET'

    if (url.includes('/api/auth/me')) {
      return jsonResponse(200, {
        id: 1,
        email: 'admin@example.com',
        is_admin: isAdmin,
        is_buyer: true,
        is_seller: false,
      })
    }
    const listMatch = url.match(/\/api\/admin\/verifications\?status=(\w+)$/)
    if (listMatch && method === 'GET') {
      return jsonResponse(200, byStatus[listMatch[1]] ?? [])
    }
    if (url.match(/\/api\/admin\/verifications\/\d+\/approve$/) && method === 'POST') {
      return jsonResponse(200, { ...PENDING_ROW, verification_status: 'verified' })
    }
    if (url.match(/\/api\/admin\/verifications\/\d+\/reject$/) && method === 'POST') {
      return jsonResponse(200, { ...PENDING_ROW, verification_status: 'rejected' })
    }
    if (url.match(/\/api\/verification\/documents\/\d+$/) && method === 'GET') {
      return new Response(new Blob(['bytes'], { type: 'application/pdf' }), {
        status: 200,
        headers: { 'Content-Type': 'application/pdf' },
      })
    }
    return jsonResponse(404, { detail: 'unexpected call in test', code: 'not_found' })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppShell />
    </MemoryRouter>,
  )
}

describe('AdminVerificationQueue', () => {
  beforeEach(() => {
    authStore.logout()
    localStorage.setItem('token', 'a.b.c')
    vi.stubGlobal(
      'URL',
      Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:mock'), revokeObjectURL: vi.fn() }),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('an admin sees the pending queue with buyer profile fields and documents', async () => {
    stubApi({ isAdmin: true })
    renderAt('/admin/verifications')

    await waitFor(() => expect(screen.getByText('Jordan Buyer')).toBeInTheDocument())
    expect(screen.getByText('jordan@example.com')).toBeInTheDocument()
    expect(screen.getByText(/250,?000/)).toBeInTheDocument()
    // `/saas/i` alone matches both the industries line and "two SaaS exits"
    // in `experience` below — the same overlap AccessRequestQueue.test.tsx
    // documents; narrowed to the industries line's own text.
    expect(screen.getByText('saas')).toBeInTheDocument()
    expect(screen.getByText(/former operator of two saas exits/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /bank-statement\.pdf/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^approve$/i })).toBeInTheDocument()
  })

  it('a non-admin is redirected away and sees no queue', async () => {
    stubApi({ isAdmin: false, byStatus: { pending: [], verified: [], rejected: [] } })
    renderAt('/admin/verifications')

    await waitFor(() => expect(screen.getByText(/your listings/i)).toBeInTheDocument())
    expect(screen.queryByText('Jordan Buyer')).not.toBeInTheDocument()
  })

  it('rejecting without a reason is blocked inline, not sent to the server', async () => {
    stubApi({ isAdmin: true })
    const user = userEvent.setup({ delay: null })
    renderAt('/admin/verifications')

    await waitFor(() => expect(screen.getByText('Jordan Buyer')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /^reject$/i }))
    await user.click(screen.getByRole('button', { name: /confirm reject/i }))

    expect(await screen.findByText(/reason is required/i)).toBeInTheDocument()
    const fetchMock = fetch as unknown as { mock: { calls: unknown[][] } }
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('/reject'))).toBe(false)
  })

  it('approving calls the approve endpoint', async () => {
    const fetchMock = stubApi({ isAdmin: true })
    const user = userEvent.setup({ delay: null })
    renderAt('/admin/verifications')

    await waitFor(() => expect(screen.getByRole('button', { name: /^approve$/i })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /^approve$/i }))

    await waitFor(() => {
      const calls = fetchMock.mock.calls.map((c) => String(c[0]))
      expect(calls.some((u) => u.includes('/admin/verifications/42/approve'))).toBe(true)
    })
  })

  it('switching the filter to Verified shows a Revoke action instead of Approve', async () => {
    stubApi({
      isAdmin: true,
      byStatus: { pending: [PENDING_ROW], verified: [VERIFIED_ROW], rejected: [] },
    })
    const user = userEvent.setup({ delay: null })
    renderAt('/admin/verifications')

    await waitFor(() => expect(screen.getByText('Jordan Buyer')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /^verified$/i }))

    await waitFor(() => expect(screen.getByText('Alex Verified')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /^revoke$/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^approve$/i })).not.toBeInTheDocument()
  })

  it('a document can be downloaded with the admin\'s credentials', async () => {
    const fetchMock = stubApi({ isAdmin: true })
    const user = userEvent.setup({ delay: null })
    renderAt('/admin/verifications')

    const downloadButton = await screen.findByRole('button', { name: /bank-statement\.pdf/i })
    await user.click(downloadButton)

    await waitFor(() => {
      const call = fetchMock.mock.calls.find((c) => String(c[0]) === '/api/verification/documents/5')
      expect(call).toBeDefined()
      const headers = (call?.[1]?.headers ?? {}) as Record<string, string>
      expect(headers.Authorization).toBe('Bearer a.b.c')
    })
  })
})
