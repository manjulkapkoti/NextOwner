// A minimal fake `WebSocket` for chat tests (M6, spec 006).
//
// No new dependency: the real browser `WebSocket` API is four handlers and a
// `send`/`close` pair, so faking it is cheaper than pulling in a library for
// one class. Install with `vi.stubGlobal('WebSocket', FakeWebSocket)` so
// `chatStore`'s real `new WebSocket(url)` call constructs one of these; drive
// the "server" side with `instance.serverOpen()` / `serverMessage()` /
// `serverClose()` — mirroring how `RequestAccessPanel.test.tsx` drives the
// "server" side of `fetch` with a stub rather than a real backend.
export class FakeWebSocket {
  static instances: FakeWebSocket[] = []

  url: string
  readyState = 0 // CONNECTING
  sent: string[] = []
  onopen: ((ev: Event) => void) | null = null
  onmessage: ((ev: MessageEvent) => void) | null = null
  onclose: ((ev: CloseEvent) => void) | null = null
  onerror: ((ev: Event) => void) | null = null

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }

  send(data: string) {
    this.sent.push(data)
  }

  close(code = 1000, reason = '') {
    this.readyState = 3 // CLOSED
    this.onclose?.({ code, reason } as CloseEvent)
  }

  // ── Test-side driving ────────────────────────────────────────────────────

  serverOpen() {
    this.readyState = 1 // OPEN
    this.onopen?.(new Event('open'))
  }

  serverMessage(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent)
  }

  serverClose(code: number, reason = '') {
    this.readyState = 3
    this.onclose?.({ code, reason } as CloseEvent)
  }

  static reset() {
    FakeWebSocket.instances = []
  }

  static last(): FakeWebSocket {
    const instance = FakeWebSocket.instances[FakeWebSocket.instances.length - 1]
    if (!instance) throw new Error('no FakeWebSocket was constructed')
    return instance
  }
}
