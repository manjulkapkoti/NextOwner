// M9 — watchlistStore (spec 009). Regression for a gap the independent
// appsec pass on PR #48 found: `remove()` threw on a 404 (a double-click, or
// a race with another tab having already removed the same entry) before
// reaching the line that filters `entries`, so the UI kept showing the
// listing as favorited even though the server already agreed it wasn't.
// A 404 on `remove` is D1's "already gone" case, not a failure — it should
// reach the same local-state update a clean 204 does. Any other failure
// (a real 500, a network error) must still propagate, not be swallowed here.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { watchlistStore } from './watchlistStore'

const ENTRY = {
  listing_id: 7,
  added_at: '2026-07-26T00:00:00Z',
  type: 'saas',
  headline: 'Profitable B2B scheduling SaaS',
  description: 'A small, profitable scheduling tool for clinics.',
  asking_price: '500000.00',
  ttm_revenue: '200000.00',
  ttm_profit: '120000.00',
  mrr: '18000.00',
  churn_pct: '2.50',
  customers: 340,
  published_at: '2026-07-01T00:00:00Z',
}

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('watchlistStore', () => {
  beforeEach(() => localStorage.setItem('token', 'a.b.c'))
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
    watchlistStore.reset()
  })

  it('remove: a 404 (already gone) still clears the entry locally, not just a 204', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, [ENTRY])))
    await watchlistStore.load()
    expect(watchlistStore.isWatchlisted(7)).toBe(true)

    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(404, { detail: 'Watchlist entry not found', code: 'not_found' }),
      ),
    )

    await expect(watchlistStore.remove(7)).resolves.toBeUndefined()
    expect(watchlistStore.isWatchlisted(7)).toBe(false)
  })

  it('remove: a real failure (500) still throws and leaves the entry in place', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, [ENTRY])))
    await watchlistStore.load()
    expect(watchlistStore.isWatchlisted(7)).toBe(true)

    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(500, { detail: 'Internal Server Error', request_id: 'req_1' }),
      ),
    )

    await expect(watchlistStore.remove(7)).rejects.toThrow()
    // A genuine failure must not be mistaken for "already removed" —
    // the entry stays, which is the honest reflection of "that didn't work".
    expect(watchlistStore.isWatchlisted(7)).toBe(true)
  })
})
