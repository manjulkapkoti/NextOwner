// M6 — chatStore (spec 006). Unit tests against the real singleton, mirroring
// accessStore.test.ts's approach: stub `fetch` (and here, `WebSocket`) and
// drive the store directly rather than through a rendered component, since
// this is the layer where the WS lifecycle and the close-code mapping (X3)
// actually live.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { chatStore } from './chatStore'
import { FakeWebSocket } from '../testUtils/fakeWebSocket'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('chatStore', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'a.b.c')
    vi.stubGlobal('WebSocket', FakeWebSocket)
    FakeWebSocket.reset()
    chatStore.reset()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('loadConversations: populates the list from GET /api/conversations', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(200, [
          { id: 1, listing_id: 7, listing_headline: 'A SaaS', counterpart_display_name: 'Jordan', unread_count: 2, last_message_at: null },
        ]),
      ),
    )

    await chatStore.loadConversations()

    expect(chatStore.conversations).toHaveLength(1)
    expect(chatStore.conversations[0].unread_count).toBe(2)
  })

  it('connect: carries the token as a query param, never a header (D6)', () => {
    chatStore.connect(1)
    const socket = FakeWebSocket.last()
    expect(socket.url).toContain('/ws/conversations/1')
    expect(socket.url).toContain('token=a.b.c')
  })

  it('connect: an open socket moves status to connected', () => {
    chatStore.connect(1)
    FakeWebSocket.last().serverOpen()
    expect(chatStore.status).toBe('connected')
  })

  it('J3/D4: a message frame is appended to messages, sender included', () => {
    chatStore.connect(1)
    const socket = FakeWebSocket.last()
    socket.serverOpen()

    socket.serverMessage({ type: 'message', id: 9, conversation_id: 1, sender_id: 2, text: 'hi', created_at: '2026-07-20T00:00:00Z' })

    expect(chatStore.messages).toHaveLength(1)
    expect(chatStore.messages[0].text).toBe('hi')
  })

  it('an error frame is not appended to messages', () => {
    chatStore.connect(1)
    const socket = FakeWebSocket.last()
    socket.serverOpen()

    socket.serverMessage({ type: 'error', code: 'message_too_long' })

    expect(chatStore.messages).toHaveLength(0)
  })

  it('send: writes {text} only — no client-guessed id, sender, or timestamp', () => {
    chatStore.connect(1)
    const socket = FakeWebSocket.last()
    socket.serverOpen()

    chatStore.send('hello there')

    expect(JSON.parse(socket.sent[0])).toEqual({ text: 'hello there' })
  })

  it.each([
    [4001, /log in again/i],
    [4003, /no longer have access/i],
    [4004, /revoked/i],
    [4009, /too fast/i],
  ])('X3: close code %i maps to a specific closeReason', (code, expected) => {
    chatStore.connect(1)
    const socket = FakeWebSocket.last()
    socket.serverOpen()
    socket.serverClose(code)

    expect(chatStore.status).toBe('closed')
    expect(chatStore.closeReason).toMatch(expected)
  })

  it('X3: a normal close (1000) shows nothing', () => {
    chatStore.connect(1)
    const socket = FakeWebSocket.last()
    socket.serverOpen()
    socket.serverClose(1000)

    expect(chatStore.closeReason).toBeNull()
  })

  it('markRead: POSTs the read receipt', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await chatStore.markRead(1)

    const calls = fetchMock.mock.calls.map((c) => String(c[0]))
    expect(calls.some((u) => u.match(/\/conversations\/1\/read$/))).toBe(true)
  })
})
