// MobX verification store (M10, spec 010) — the buyer's own proof-of-funds
// state, as GET /api/verification reports it.
//
// Structurally close to watchlistStore (M9): no gate to interpret client-side
// (unlike accessStore's 403-is-a-state distinction) — `verification_status`
// is just data the server owns, and the one client-visible rule (D3: no
// upload once `verified`) is UX only, mirrored by the caller
// (VerificationStatus.tsx) rather than by this store. The server's 409
// `already_verified` remains the real boundary if the client is wrong or
// stale.
import { makeAutoObservable, runInAction } from 'mobx'
import { api } from '../lib/api'

export type VerificationStatusValue = 'unverified' | 'pending' | 'verified' | 'rejected'

// Mirrors `VerificationDocumentRead` in backend/app/schemas.py exactly — no
// `storage_key` (S9, an internal path component never sent to the client).
export interface VerificationDocument {
  id: number
  original_filename: string
  content_type: string
  size_bytes: number
  uploaded_at: string
}

interface VerificationReadResponse {
  verification_status: VerificationStatusValue
  verification_reviewed_at: string | null
  verification_reason: string | null
  documents: VerificationDocument[]
}

class VerificationStore {
  status: VerificationStatusValue = 'unverified'
  reviewedAt: string | null = null
  reason: string | null = null
  documents: VerificationDocument[] = []
  loading = false
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
      const data = (await api('/verification')) as VerificationReadResponse
      runInAction(() => {
        this.status = data.verification_status
        this.reviewedAt = data.verification_reviewed_at
        this.reason = data.verification_reason
        this.documents = data.documents
        this.loaded = true
      })
    } catch {
      runInAction(() => {
        this.error = 'We could not load your verification status.'
      })
    } finally {
      runInAction(() => {
        this.loading = false
      })
    }
  }

  /** POST then refetch (mirrors the M2 upload-then-refetch shape, plan.md §
   * Frontend): the response is just the new document, and the status/reason
   * transition it may have triggered (D1) is the server's to report, not this
   * client's to guess at. Errors (409 already_verified, 415, 413, 422)
   * propagate to the caller, which is the one that knows how to word them. */
  async upload(file: File): Promise<void> {
    const formData = new FormData()
    formData.append('file', file)
    await api('/verification/documents', { method: 'POST', body: formData })
    await this.load()
  }

  reset(): void {
    this.status = 'unverified'
    this.reviewedAt = null
    this.reason = null
    this.documents = []
    this.loading = false
    this.loaded = false
    this.error = null
  }
}

export const verificationStore = new VerificationStore()
