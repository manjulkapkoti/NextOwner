// MobX watchlist store (M9, spec 009) — a buyer's favorited listings.
//
// Structurally the simplest store in the app: unlike accessStore there is no
// gate to interpret (a watchlist entry has no state machine, spec D1) — the
// three server routes are plain boolean-membership operations, so there is no
// "403 is a state, not an error" distinction to preserve here.
//
// Client state is convenience only; the server (`get_owned_watchlist_entry`,
// the D2 live-listing check) is the real boundary.
import { makeAutoObservable, runInAction } from 'mobx'
import { api } from '../lib/api'

// Mirrors `WatchlistEntryRead` in backend/app/schemas.py exactly — note
// `listing_id`, not `id`, and no `owner_id` / `status` / `company_name` /
// `website_url` / `detailed_financials` (excluded by the server by schema).
export interface WatchlistEntryRead {
  listing_id: number
  added_at: string
  type: string
  headline: string
  description: string
  asking_price: string
  ttm_revenue: string
  ttm_profit: string
  mrr: string
  churn_pct: string
  customers: number
  published_at: string | null
}

class WatchlistStore {
  entries: WatchlistEntryRead[] = []
  loading = false
  // Lets callers (WatchlistButton, instantiated once per card on a grid of
  // many listings) avoid triggering a redundant fetch per instance.
  loaded = false
  error: string | null = null

  constructor() {
    makeAutoObservable(this)
  }

  async load(): Promise<void> {
    runInAction(() => {
      this.loading = true
      this.error = null
    })
    try {
      const rows = (await api('/watchlist')) as WatchlistEntryRead[]
      runInAction(() => {
        this.entries = rows
        this.loaded = true
      })
    } catch {
      runInAction(() => {
        this.error = 'We could not load your watchlist.'
      })
    } finally {
      runInAction(() => {
        this.loading = false
      })
    }
  }

  /** POST is idempotent server-side (spec D1) — simplest correct client
   * behavior is to re-fetch rather than guess at the returned row's shape;
   * this is not a hot path. */
  async add(listingId: number): Promise<void> {
    await api(`/watchlist/${listingId}`, { method: 'POST' })
    await this.load()
  }

  /** No re-fetch needed: the caller's own delete is the only thing that could
   * have changed the list, so removing the row locally keeps this fast. */
  async remove(listingId: number): Promise<void> {
    await api(`/watchlist/${listingId}`, { method: 'DELETE' })
    runInAction(() => {
      this.entries = this.entries.filter((entry) => entry.listing_id !== listingId)
    })
  }

  isWatchlisted(listingId: number): boolean {
    return this.entries.some((entry) => entry.listing_id === listingId)
  }

  reset(): void {
    this.entries = []
    this.loading = false
    this.loaded = false
    this.error = null
  }
}

export const watchlistStore = new WatchlistStore()
