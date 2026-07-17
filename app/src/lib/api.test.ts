// M1 — the api client throws a typed ApiError (spec 001 acceptance criterion H2).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'

describe('api() error handling', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => vi.unstubAllGlobals())

  it('throws a typed ApiError carrying status and code, not a bare Error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: 'no', code: 'unauthorized' }), {
            status: 401,
            headers: { 'Content-Type': 'application/json' },
          }),
      ),
    )
    await expect(api('/auth/me')).rejects.toMatchObject({
      status: 401,
      code: 'unauthorized',
    })
    await expect(api('/auth/me')).rejects.toBeInstanceOf(ApiError)
  })
})
