// M6 — the conversation list (spec 006 criterion J2).
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ConversationList } from './ConversationList'
import { chatStore } from '../stores/chatStore'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function stubConversations(rows: unknown[]) {
  vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, rows)))
}

function renderList() {
  return render(
    <MemoryRouter initialEntries={['/messages']}>
      <Routes>
        <Route path="/messages" element={<ConversationList />} />
        <Route path="/messages/:id" element={<div>Chat window 3</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ConversationList', () => {
  beforeEach(() => localStorage.setItem('token', 'a.b.c'))
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
    chatStore.reset()
  })

  it('J2: shows the listing headline, counterpart name, and unread badge; clicking opens that chat', async () => {
    stubConversations([
      {
        id: 3,
        listing_id: 7,
        listing_headline: 'A SaaS business',
        counterpart_display_name: 'Jordan Buyer',
        unread_count: 2,
        last_message_at: '2026-07-20T00:00:00Z',
      },
    ])
    renderList()

    expect(await screen.findByText('A SaaS business')).toBeInTheDocument()
    expect(screen.getByText('Jordan Buyer')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()

    await userEvent.click(screen.getByText('A SaaS business'))
    expect(await screen.findByText('Chat window 3')).toBeInTheDocument()
  })

  it('shows an empty state with no conversations', async () => {
    stubConversations([])
    renderList()

    await waitFor(() => expect(screen.getByText(/no conversations yet/i)).toBeInTheDocument())
  })
})
