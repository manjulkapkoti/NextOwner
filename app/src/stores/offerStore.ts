// M7 — offers/LOI, the client's view of the bilateral negotiation (spec 007).
//
// Mirrors `accessStore.ts`'s own framing (M5): state is convenience only, the
// server's gates (`require_approved_buyer`, `require_offer_party`) are the
// real boundary. Two arrays only:
//  - `myOffers` — the buyer's own rows across every listing (`GET /my/offers`).
//  - `listingOffers` — one listing's full queue, each row carrying the
//    buyer's profile (`GET /my/listings/{id}/offers`), for the seller.
//
// **State source discipline (the RequestAccessPanel lesson, spec 005 J2):** a
// POST response only knows about the row it just changed, not the rest of a
// negotiation thread. So `accept`/`decline`/`counter`/`withdraw` here do
// exactly one thing — POST and hand back the parsed row — and never patch
// `myOffers`/`listingOffers` themselves. The one exception is `createOffer`,
// which *does* fold its new row into `myOffers` (there is no server list to
// re-read from that would be cheaper than the row already in hand). Every
// other mutation's caller (`OfferThread`, via its `onChange` prop) is
// responsible for re-fetching — the same "re-read from the server rather than
// patching local state" rule `AccessRequestQueue.decide()` already follows.
import { makeAutoObservable, runInAction } from 'mobx'
import { api } from '../lib/api'

export interface OfferTerms {
  price: string
  structure: string
  contingencies: string | null
  proposed_close_date: string
}

export type OfferRole = 'buyer' | 'seller'
export type OfferStatus = 'submitted' | 'accepted' | 'declined' | 'withdrawn' | 'countered'

export interface OfferRead extends OfferTerms {
  id: number
  listing_id: number
  parent_offer_id: number | null
  proposed_by_role: OfferRole
  status: OfferStatus
  created_at: string
  decided_at: string | null
}

export interface BuyerProfile {
  display_name: string | null
  budget: string | number | null
  // The API sends a string today; an array is tolerated so the shape can grow
  // into structured sectors without this component becoming the blocker
  // (mirrors AccessRequestQueue's own BuyerProfile — spec 005).
  target_industries: string | string[] | null
  experience: string | null
}

export interface OfferWithBuyer extends OfferRead {
  // Present on the real API response (G1); optional here only so a test
  // fixture that omits it still type-checks the same way `AccessRequestQueue`
  // tolerates a looser shape than the wire contract.
  buyer_id?: number
  buyer: BuyerProfile
}

class OfferStore {
  myOffers: OfferRead[] = []
  listingOffers: OfferWithBuyer[] = []

  constructor() {
    makeAutoObservable(this)
  }

  /** The buyer's own rows, across every listing (F1-F3). */
  async loadMyOffers(): Promise<void> {
    const rows = (await api('/my/offers')) as OfferRead[]
    runInAction(() => {
      this.myOffers = rows
    })
  }

  /** One listing's own thread, in oldest-first order (mirrors the chain). */
  offersForListing(listingId: number): OfferRead[] {
    return this.myOffers
      .filter((row) => row.listing_id === listingId)
      .slice()
      .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))
  }

  /** The seller's queue for one listing — every buyer's full thread (G1). */
  async loadListingOffers(listingId: number): Promise<void> {
    const rows = (await api(`/my/listings/${listingId}/offers`)) as OfferWithBuyer[]
    runInAction(() => {
      this.listingOffers = rows
    })
  }

  /** J1 — submit a new offer. Folds the row straight into `myOffers`: it is
   * the one write this store trusts from its own POST response, because there
   * is nothing cheaper to re-fetch (this *is* the whole new row). */
  async createOffer(listingId: number, terms: OfferTerms): Promise<OfferRead> {
    const row = (await api(`/listings/${listingId}/offers`, {
      method: 'POST',
      body: JSON.stringify(terms),
    })) as OfferRead
    runInAction(() => {
      this.myOffers = [...this.myOffers, row]
    })
    return row
  }

  async accept(offerId: number): Promise<OfferRead> {
    return (await api(`/offers/${offerId}/accept`, { method: 'POST' })) as OfferRead
  }

  async decline(offerId: number): Promise<OfferRead> {
    return (await api(`/offers/${offerId}/decline`, { method: 'POST' })) as OfferRead
  }

  async withdraw(offerId: number): Promise<OfferRead> {
    return (await api(`/offers/${offerId}/withdraw`, { method: 'POST' })) as OfferRead
  }

  async counter(offerId: number, terms: OfferTerms): Promise<OfferRead> {
    return (await api(`/offers/${offerId}/counter`, {
      method: 'POST',
      body: JSON.stringify(terms),
    })) as OfferRead
  }

  reset(): void {
    this.myOffers = []
    this.listingOffers = []
  }
}

export const offerStore = new OfferStore()
