// The single API client — replaces any BaaS SDK (design_implementation.md §3.4).
// The URL is RELATIVE (`/api...`) so it's same-origin: in dev the Vite proxy
// forwards to FastAPI, in prod a reverse proxy does. The JWT (once auth lands
// in M1) rides along in the Authorization header.
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
    // Surface the server's generic detail message; never leak internals.
    const detail = await res
      .json()
      .then((b) => b?.detail)
      .catch(() => null)
    throw new Error(detail ?? res.statusText)
  }
  return res.status === 204 ? null : res.json()
}
