// M6 — the chat window (spec 006 criteria J3, J4, J5, X2).
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatWindow } from './ChatWindow'
import { chatStore } from '../stores/chatStore'
import { authStore } from '../stores/authStore'
import { FakeWebSocket } from '../testUtils/fakeWebSocket'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function stubFetch({ history = [] as unknown[] } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    if (url.match(/\/messages(\?.*)?$/) && method === 'GET') return jsonResponse(200, history)
    if (url.match(/\/read$/) && method === 'POST') return new Response(null, { status: 204 })
    return jsonResponse(404, { detail: 'unexpected call in test', code: 'not_found' })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('ChatWindow', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'a.b.c')
    authStore.user = {
      id: 2,
      email: 'buyer@example.com',
      is_buyer: true,
      is_seller: false,
      is_admin: false,
      display_name: 'Jordan Buyer',
    } as unknown as typeof authStore.user
    vi.stubGlobal('WebSocket', FakeWebSocket)
    FakeWebSocket.reset()
    chatStore.reset()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
    authStore.logout()
  })

  it('J3: renders history oldest-first, distinguishing mine vs theirs by sender_id', async () => {
    stubFetch({
      history: [
        { id: 2, conversation_id: 1, sender_id: 3, text: 'seller says hi', created_at: '2026-07-20T00:01:00Z' },
        { id: 1, conversation_id: 1, sender_id: 2, text: 'buyer says hi', created_at: '2026-07-20T00:00:00Z' },
      ],
    })
    render(<ChatWindow conversationId={1} />)

    const mine = await screen.findAllByTestId('message-mine')
    const theirs = screen.getAllByTestId('message-theirs')
    expect(mine).toHaveLength(1)
    expect(theirs).toHaveLength(1)

    const order = screen.getAllByText(/says hi/).map((el) => el.textContent)
    expect(order).toEqual(['buyer says hi', 'seller says hi'])
  })

  it('J4: XSS — markup in a message renders as literal text, never executed', async () => {
    stubFetch({
      history: [
        { id: 1, conversation_id: 1, sender_id: 3, text: '<script>alert(1)</script>', created_at: '2026-07-20T00:00:00Z' },
      ],
    })
    render(<ChatWindow conversationId={1} />)

    expect(await screen.findByText('<script>alert(1)</script>')).toBeInTheDocument()
    expect(document.querySelectorAll('script')).toHaveLength(0)
  })

  it('J5: sending clears the input; the message appears only once the server echo arrives', async () => {
    stubFetch()
    const user = userEvent.setup({ delay: null })
    render(<ChatWindow conversationId={1} />)
    FakeWebSocket.last().serverOpen()

    const input = await screen.findByRole('textbox')
    await user.type(input, 'hello')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(input).toHaveValue('')
    expect(screen.queryByText('hello')).not.toBeInTheDocument()

    FakeWebSocket.last().serverMessage({
      type: 'message',
      id: 9,
      conversation_id: 1,
      sender_id: 2,
      text: 'hello',
      created_at: '2026-07-20T00:00:00Z',
    })

    expect(await screen.findByText('hello')).toBeInTheDocument()
  })

  it('X2: shows an empty state with no messages yet', async () => {
    stubFetch({ history: [] })
    render(<ChatWindow conversationId={1} />)

    expect(await screen.findByText(/no messages yet/i)).toBeInTheDocument()
  })

  it('X2/X3: a revoked-access close renders a distinct banner, not a crash', async () => {
    stubFetch({ history: [] })
    render(<ChatWindow conversationId={1} />)
    await screen.findByText(/no messages yet/i)

    FakeWebSocket.last().serverOpen()
    FakeWebSocket.last().serverClose(4004)

    expect(await screen.findByText(/revoked/i)).toBeInTheDocument()
  })
})
