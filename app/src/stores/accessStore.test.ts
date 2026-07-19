// M5 — accessStore (spec 005 criterion J5; plan.md § Frontend: "must not
// treat a 403 as a global-401").
//
// `api.ts` fires the `auth:unauthorized` redirect-to-login event on 401 only
// (spec 001 H5) — that behaviour is already proven in `lib/api.test.ts`. This
// store's own risk is different: a 403 `nda_access_required` is a completely
// normal, expected outcome of the gate (D3–D6), not a session failure, so
// nothing in this store may react to it the way the app reacts to a dead
// token. Tested directly at the store layer — the layer where that
// conflation would actually happen — rather than only inferred from a
// component's rendered output.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { accessStore } from './accessStore'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('accessStore', () => {
  beforeEach(() => localStorage.setItem('token', 'a.b.c'))
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('loadPrivate: a 200 unlocks the store and keeps the private payload', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(200, {
          company_name: 'Acme Internal Tools LLC',
          website_url: 'https://acme.example.com',
          detailed_financials: 'Full P&L available on request.',
        }),
      ),
    )

    await accessStore.loadPrivate(7).catch(() => {})

    expect(accessStore.status).toBe('unlocked')
    expect(accessStore.privateData?.company_name).toBe('Acme Internal Tools LLC')
  })

  it('J5: a 403 nda_access_required locks the store without touching the global-401 handler', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(403, {
          detail: 'You do not have access to this data room.',
          code: 'nda_access_required',
          request_id: 'req_1',
        }),
      ),
    )
    const onUnauthorized = vi.fn()
    window.addEventListener('auth:unauthorized', onUnauthorized)

    await accessStore.loadPrivate(7).catch(() => {})

    expect(accessStore.status).not.toBe('error')
    expect(accessStore.status).not.toBe('unlocked')
    expect(onUnauthorized).not.toHaveBeenCalled()
    // A 403 must never be treated as a dead session — the token stays.
    expect(localStorage.getItem('token')).toBe('a.b.c')

    window.removeEventListener('auth:unauthorized', onUnauthorized)
  })

  it('a real 401 still reaches the existing global handler — the store does not blanket-swallow every error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse(401, { detail: 'Not authenticated', code: 'unauthorized' })),
    )
    const onUnauthorized = vi.fn()
    window.addEventListener('auth:unauthorized', onUnauthorized)

    await accessStore.loadPrivate(7).catch(() => {})

    expect(onUnauthorized).toHaveBeenCalled()
    expect(localStorage.getItem('token')).toBeNull()

    window.removeEventListener('auth:unauthorized', onUnauthorized)
  })
})
