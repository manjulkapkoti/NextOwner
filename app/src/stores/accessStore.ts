// MobX access store — the NDA gate as the client sees it (M5, spec 005).
//
// The one rule this file exists to hold: **a 403 is not a 401.** `api.ts` drops
// the token and fires `auth:unauthorized` on 401, which is right for a dead
// session and catastrophic for a locked data room — a perfectly logged-in buyer
// would be bounced to /login for the entirely normal outcome of not having been
// approved yet. So every gate call catches `ApiError` and branches on `status`,
// and `nda_access_required` resolves to a *state*, not an error.
//
// Client state is convenience only; the server gate is the real boundary.
import { makeAutoObservable, runInAction } from 'mobx'
import { ApiError, api } from '../lib/api'

export interface ListingPrivate {
  listing_id: number
  company_name: string
  website_url: string
  detailed_financials: string | null
}

export interface DataRoomDocument {
  id: number
  original_filename: string
  content_type: string
  size_bytes: number
  uploaded_at: string
}

export interface MyAccessRequest {
  id: number
  listing_id: number
  status: 'requested' | 'approved' | 'denied' | 'revoked'
  created_at: string
}

/** What the buyer's UI should show for one listing.
 *
 * `locked` covers "never asked" and "asked and was refused" alike on the *gate*
 * side; the request list refines it to `denied`/`revoked` when a row says so.
 * `error` is reserved for a genuine failure — never for a 403, which is the
 * gate working correctly.
 */
export type AccessStatus =
  | 'idle'
  | 'loading'
  | 'locked'
  | 'pending'
  | 'denied'
  | 'unlocked'
  | 'error'

class AccessStore {
  status: AccessStatus = 'idle'
  privateData: ListingPrivate | null = null
  documents: DataRoomDocument[] = []
  myRequests: MyAccessRequest[] = []

  constructor() {
    makeAutoObservable(this)
  }

  /** The buyer's own requests — the source of pending/denied across reloads.
   *
   * A POST response only knows about the current session, so a returning buyer
   * would be shown "Request access" for a request they already made (and get a
   * 409 for clicking it). This is why the panel reads the list on mount.
   */
  async loadMyRequests(): Promise<void> {
    const rows = (await api('/my/access-requests')) as MyAccessRequest[]
    runInAction(() => {
      this.myRequests = rows
    })
  }

  requestFor(listingId: number): MyAccessRequest | undefined {
    return this.myRequests.find((row) => row.listing_id === listingId)
  }

  /** The data room's file index — fetched only once the gate has opened.
   *
   * Behind `require_private_access` server-side, exactly like the payload and
   * the downloads. Added after the M5 appsec review found the download route
   * unreachable in practice: a `doc_id` appeared nowhere a buyer could see, so
   * an approved buyer got an empty data room. The endpoint alone did not fix
   * that — this call is the other half.
   */
  async loadDocuments(listingId: number): Promise<void> {
    const rows = (await api(`/listings/${listingId}/documents`)) as DataRoomDocument[]
    runInAction(() => {
      this.documents = rows
    })
  }

  /** Fetch the data room. A 403 locks; only a real failure errors. */
  async loadPrivate(listingId: number): Promise<void> {
    runInAction(() => {
      this.status = 'loading'
    })
    try {
      const data = (await api(`/listings/${listingId}/private`)) as ListingPrivate
      runInAction(() => {
        this.privateData = data
        this.status = 'unlocked'
      })
    } catch (err) {
      runInAction(() => {
        if (err instanceof ApiError && err.status === 403) {
          // The gate did its job. Not an error — a state.
          this.status = 'locked'
        } else if (err instanceof ApiError && err.status === 401) {
          // Left alone deliberately: `api.ts` has already cleared the token and
          // fired `auth:unauthorized`. Swallowing it here would strand the user
          // on a page the app is trying to navigate away from.
          this.status = 'error'
        } else {
          this.status = 'error'
        }
      })
      throw err
    }
  }

  async signNda(): Promise<void> {
    await api('/auth/nda', { method: 'POST' })
  }

  async requestAccess(listingId: number): Promise<MyAccessRequest> {
    const row = (await api(`/listings/${listingId}/access-request`, {
      method: 'POST',
    })) as MyAccessRequest
    runInAction(() => {
      this.myRequests = [...this.myRequests.filter((r) => r.listing_id !== listingId), row]
      this.status = 'pending'
    })
    return row
  }

  reset(): void {
    this.status = 'idle'
    this.privateData = null
    this.documents = []
    this.myRequests = []
  }
}

export const accessStore = new AccessStore()
