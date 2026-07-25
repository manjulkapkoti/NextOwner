// M8 — the notification inbox + nav badge (spec 008 criteria J1-J6).
// Written failing first: NotificationInbox and NotificationBadge do not exist.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { NotificationInbox } from './NotificationInbox'
import { NavBar } from './NavBar'
import { notificationStore } from '../stores/notificationStore'
import { chatStore } from '../stores/chatStore'
import { authStore } from '../stores/authStore'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const UNREAD = {
  id: 11,
  type: 'access_approved',
  title: 'Your access request was approved',
  listing_id: 7,
  conversation_id: null,
  offer_id: null,
  read_at: null,
  created_at: '2026-07-25T10:00:00Z',
}

const READ = {
  id: 12,
  type: 'listing_matched',
  title: 'A new SaaS business matches your search',
  listing_id: 8,
  conversation_id: null,
  offer_id: null,
  read_at: '2026-07-25T11:00:00Z',
  created_at: '2026-07-25T09:00:00Z',
}

function renderInbox() {
  return render(
    <MemoryRouter initialEntries={['/notifications']}>
      <Routes>
        <Route path="/notifications" element={<NotificationInbox />} />
        <Route path="/listings/:id" element={<div>Listing detail page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('NotificationInbox', () => {
  beforeEach(() => localStorage.setItem('token', 'a.b.c'))
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
    notificationStore.reset()
    chatStore.reset()
    authStore.logout()
  })

  it('J1: lists the notifications and marks the unread ones', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, [UNREAD, READ])))
    renderInbox()

    expect(await screen.findByText(UNREAD.title)).toBeInTheDocument()
    expect(screen.getByText(READ.title)).toBeInTheDocument()
    expect(screen.getByTestId(`notification-${UNREAD.id}`)).toHaveAttribute(
      'data-unread',
      'true',
    )
    expect(screen.getByTestId(`notification-${READ.id}`)).toHaveAttribute(
      'data-unread',
      'false',
    )
  })

  // Rendered through the real `NavBar` rather than an isolated badge
  // component: the criterion is about what the nav bar shows, and testing the
  // surface the user actually sees is what makes this more than a render test.
  it('J2: the nav badge shows the unread count from the API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) =>
        String(input).includes('unread-count')
          ? jsonResponse(200, { unread_count: 4 })
          : jsonResponse(200, []),
      ),
    )
    authStore.setToken('a.b.c')
    render(
      <MemoryRouter>
        <NavBar />
      </MemoryRouter>,
    )

    expect(await screen.findByText('4')).toBeInTheDocument()
  })

  it('J3: clicking an unread notification marks it read and navigates to the target', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (init?.method === 'POST' && url.includes('/read')) {
        return jsonResponse(200, { ...UNREAD, read_at: '2026-07-25T12:00:00Z' })
      }
      return jsonResponse(200, [UNREAD])
    })
    vi.stubGlobal('fetch', fetchMock)
    renderInbox()

    await userEvent.click(await screen.findByText(UNREAD.title))

    await waitFor(() =>
      expect(screen.getByText('Listing detail page')).toBeInTheDocument(),
    )
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).includes(`/api/notifications/${UNREAD.id}/read`) &&
          (init as RequestInit | undefined)?.method === 'POST',
      ),
    ).toBe(true)
  })

  it('J4: shows an empty state rather than a blank panel', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, [])))
    renderInbox()

    expect(await screen.findByText(/no notifications/i)).toBeInTheDocument()
  })

  it('J5: shows a loading state while the request is in flight', async () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
    renderInbox()

    expect(await screen.findByRole('progressbar')).toBeInTheDocument()
  })

  it('J6: shows an error state when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(500, { detail: 'boom' })))
    renderInbox()

    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
