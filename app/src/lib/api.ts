// The single API client — replaces any BaaS SDK (design_implementation.md §3.4).
// The URL is RELATIVE (`/api...`) so it's same-origin: in dev the Vite proxy
// forwards to FastAPI, in prod a reverse proxy does. The JWT rides along in the
// Authorization header (token storage: localStorage for the local MVP — the XSS
// tradeoff is recorded in security.md §Frontend session; production moves to an
// httpOnly cookie + refresh, security.md §9).

// A typed error so callers branch on `status` / `code` instead of string-matching
// (error_handling.md §3). This is the single place an API failure becomes a
// throw, so 401 handling, retries, etc. have one home.
export class ApiError extends Error {
  readonly status: number
  readonly code: string | null
  readonly detail: unknown

  constructor(status: number, code: string | null, detail: unknown, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
  }
}

export async function api(path: string, opts: RequestInit = {}) {
  const token = localStorage.getItem('token')
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...opts.headers,
    },
  })
  if (!res.ok) {
    let body: { detail?: unknown; code?: string } | null = null
    try {
      body = await res.json()
    } catch {
      body = null
    }
    const code = body?.code ?? null
    const detail = body?.detail
    // Global 401 handling (plan.md slice 9 / security.md §3): a 401 means the
    // token is missing/expired/invalid, so drop it and signal the app to send
    // the user to login. Done here — the single API choke point — rather than
    // per-call. A window event (not an authStore import) avoids a cycle.
    if (res.status === 401) {
      localStorage.removeItem('token')
      window.dispatchEvent(new Event('auth:unauthorized'))
    }
    // Surface the server's generic detail; never leak internals.
    const message = typeof detail === 'string' ? detail : res.statusText
    throw new ApiError(res.status, code, detail, message)
  }
  return res.status === 204 ? null : res.json()
}
