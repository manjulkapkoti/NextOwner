// MobX chat store — the WebSocket lifecycle + the REST reads (M6, spec 006).
//
// Owns the one thing a component should not have to: the raw `WebSocket`.
// A component asks this store to connect/send/disconnect and reads its
// observable `messages`/`status`/`closeReason` — mirroring how `accessStore`
// (M5) is the layer that owns the NDA-gate's own state so a component never
// has to reimplement "is a 403 actually an error" logic itself.
import { makeAutoObservable, runInAction } from 'mobx'
import { api } from '../lib/api'

export interface ConversationSummary {
  id: number
  listing_id: number
  listing_headline: string
  counterpart_display_name: string | null
  unread_count: number
  last_message_at: string | null
}

export interface ChatMessage {
  id: number
  conversation_id: number
  sender_id: number
  text: string
  created_at: string
}

export type ChatConnectionStatus = 'idle' | 'loading' | 'connected' | 'closed' | 'error'

// Spec 006 § Decisions D1 — one message per close code, everything else
// shows nothing (X3). Kept here, not scattered across components, so the
// mapping has exactly one home.
const CLOSE_CODE_MESSAGES: Record<number, string> = {
  4001: 'Your session expired — please log in again.',
  4003: 'You no longer have access to this conversation.',
  4004: 'The seller revoked your access to this listing.',
  4009: "You're sending messages too fast — please slow down.",
}

class ChatStore {
  conversations: ConversationSummary[] = []
  messages: ChatMessage[] = []
  status: ChatConnectionStatus = 'idle'
  closeReason: string | null = null
  private socket: WebSocket | null = null

  constructor() {
    makeAutoObservable(this, { socket: false } as never)
  }

  async loadConversations(): Promise<void> {
    const rows = (await api('/conversations')) as ConversationSummary[]
    runInAction(() => {
      this.conversations = rows
    })
  }

  async loadHistory(conversationId: number): Promise<void> {
    const rows = (await api(`/conversations/${conversationId}/messages`)) as ChatMessage[]
    runInAction(() => {
      // The endpoint returns newest-first (spec 006 G1); the window renders
      // oldest-first (J3), so this is the one place that ordering flips.
      this.messages = [...rows].reverse()
    })
  }

  async markRead(conversationId: number): Promise<void> {
    await api(`/conversations/${conversationId}/read`, { method: 'POST' })
  }

  /** Carries the token as a query param, never a header (D6 — a browser
   * cannot attach a custom header to a WebSocket handshake). */
  connect(conversationId: number): void {
    runInAction(() => {
      this.status = 'loading'
      this.closeReason = null
    })
    const token = localStorage.getItem('token') ?? ''
    const socket = new WebSocket(`/ws/conversations/${conversationId}?token=${encodeURIComponent(token)}`)

    socket.onopen = () => {
      runInAction(() => {
        this.status = 'connected'
      })
    }
    socket.onmessage = (event) => {
      let frame: { type?: string; [key: string]: unknown }
      try {
        frame = JSON.parse(event.data as string)
      } catch {
        return
      }
      if (frame.type === 'message') {
        runInAction(() => {
          this.messages = [...this.messages, frame as unknown as ChatMessage]
        })
      }
      // Error frames (invalid_message / message_too_long) are non-fatal by
      // design (spec 006 D1-D3) — nothing to surface at the store level; the
      // input simply was not sent.
    }
    socket.onclose = (event) => {
      runInAction(() => {
        this.status = 'closed'
        this.closeReason = CLOSE_CODE_MESSAGES[event.code] ?? null
      })
    }

    this.socket = socket
  }

  disconnect(): void {
    this.socket?.close()
    this.socket = null
  }

  /** Writes `{text}` only — no client-guessed id, sender, or timestamp
   * (security.md §1.5: identity comes from the connection, never the payload). */
  send(text: string): void {
    this.socket?.send(JSON.stringify({ text }))
  }

  reset(): void {
    this.disconnect()
    this.conversations = []
    this.messages = []
    this.status = 'idle'
    this.closeReason = null
  }
}

export const chatStore = new ChatStore()
