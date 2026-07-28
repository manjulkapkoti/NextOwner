// M10 — the buyer's own verification page (spec 010 § Frontend).
//
// Covers the empty/loading/error triad (docs/error_handling.md §3), the
// upload form's absence once `verified` (D3, mirrored client-side), the
// rejection reason surfacing (V5), and the 409/413/415 upload error messages
// distinguished by the `code` field rather than a generic toast.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { VerificationStatus } from './VerificationStatus'
import { verificationStore } from '../stores/verificationStore'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

interface StubState {
  status: string
  reason: string | null
  reviewedAt: string | null
  documents: Array<{
    id: number
    original_filename: string
    content_type: string
    size_bytes: number
    uploaded_at: string
  }>
}

function stubVerification(initial: Partial<StubState> = {}) {
  const state: StubState = {
    status: 'unverified',
    reason: null,
    reviewedAt: null,
    documents: [],
    ...initial,
  }
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    if (url.endsWith('/api/verification') && method === 'GET') {
      return jsonResponse(200, {
        verification_status: state.status,
        verification_reviewed_at: state.reviewedAt,
        verification_reason: state.reason,
        documents: state.documents,
      })
    }
    if (url.endsWith('/api/verification/documents') && method === 'POST') {
      const doc = {
        id: state.documents.length + 1,
        original_filename: 'proof.pdf',
        content_type: 'application/pdf',
        size_bytes: 12345,
        uploaded_at: '2026-07-27T00:00:00Z',
      }
      state.documents = [...state.documents, doc]
      state.status = 'pending'
      state.reason = null
      state.reviewedAt = null
      return jsonResponse(201, doc)
    }
    return jsonResponse(404, { detail: 'unexpected call in test', code: 'not_found' })
  })
  vi.stubGlobal('fetch', fetchMock)
  return { fetchMock, state }
}

function stubUploadError(status: number, code: string | null, detail = 'refused') {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    if (url.endsWith('/api/verification') && method === 'GET') {
      return jsonResponse(200, {
        verification_status: 'unverified',
        verification_reviewed_at: null,
        verification_reason: null,
        documents: [],
      })
    }
    if (url.endsWith('/api/verification/documents') && method === 'POST') {
      return jsonResponse(status, { detail, code })
    }
    return jsonResponse(404, { detail: 'unexpected call in test', code: 'not_found' })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const PDF = new File(['file bytes'], 'proof.pdf', { type: 'application/pdf' })

describe('VerificationStatus', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'a.b.c')
    vi.stubGlobal(
      'URL',
      Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:mock'), revokeObjectURL: vi.fn() }),
    )
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
    verificationStore.reset()
  })

  it('shows a loading state before the status resolves', async () => {
    // A fetch that never resolves during the assertion window — the loading
    // skeleton must appear and then persist, since nothing here ever settles.
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
    render(<VerificationStatus />)
    await waitFor(() =>
      expect(screen.getByRole('status', { name: /loading your verification status/i })).toBeInTheDocument(),
    )
  })

  it('shows an error alert when the load fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(500, { detail: 'Internal error' })))
    render(<VerificationStatus />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })

  it('an unverified buyer sees the Unverified status, no documents, and an upload form', async () => {
    stubVerification({ status: 'unverified' })
    render(<VerificationStatus />)

    await waitFor(() => expect(screen.getByText('Unverified')).toBeInTheDocument())
    expect(screen.getByText(/no documents submitted yet/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /choose file/i })).toBeInTheDocument()
  })

  it('a rejected buyer sees the reason and a resubmit form', async () => {
    stubVerification({ status: 'rejected', reason: 'Statement was illegible.' })
    render(<VerificationStatus />)

    await waitFor(() => expect(screen.getByText('Rejected')).toBeInTheDocument())
    expect(screen.getByText(/statement was illegible/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /choose file/i })).toBeInTheDocument()
  })

  // D3, mirrored client-side: the upload control is hidden — not merely
  // disabled — once verified, matching the server's 409 already_verified.
  it('a verified buyer sees no upload control', async () => {
    stubVerification({ status: 'verified', reviewedAt: '2026-07-20T00:00:00Z' })
    render(<VerificationStatus />)

    await waitFor(() => expect(screen.getByText('Verified')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /choose file/i })).not.toBeInTheDocument()
    expect(screen.getByText(/you're verified/i)).toBeInTheDocument()
  })

  it('uploading a file posts multipart form data and refreshes the status to pending', async () => {
    const { fetchMock } = stubVerification({ status: 'unverified' })
    const user = userEvent.setup({ delay: null })
    render(<VerificationStatus />)

    const input = await screen.findByLabelText(/upload proof of funds document/i)
    await user.upload(input, PDF)

    await waitFor(() => expect(screen.getByText('Pending review')).toBeInTheDocument())

    const uploadCall = fetchMock.mock.calls.find(
      (c) => String(c[0]).endsWith('/api/verification/documents'),
    )
    expect(uploadCall).toBeDefined()
    const [, init] = uploadCall as [string, RequestInit]
    expect(init.body).toBeInstanceOf(FormData)
    // The api.ts wrapper must not force a JSON Content-Type onto a multipart
    // body — that would strip the browser-generated boundary the server needs
    // to parse it at all (see api.ts's isFormData branch).
    const headers = (init.headers ?? {}) as Record<string, string>
    expect(headers['Content-Type']).toBeUndefined()
  })

  it('409 already_verified surfaces a specific banner, not a generic failure', async () => {
    stubUploadError(409, 'already_verified')
    const user = userEvent.setup({ delay: null })
    render(<VerificationStatus />)

    const input = await screen.findByLabelText(/upload proof of funds document/i)
    await user.upload(input, PDF)

    expect(await screen.findByText(/already verified/i)).toBeInTheDocument()
  })

  it('413 upload_quota_exceeded is distinguished from a plain file-too-large 413', async () => {
    stubUploadError(413, 'upload_quota_exceeded')
    const user = userEvent.setup({ delay: null })
    render(<VerificationStatus />)

    const input = await screen.findByLabelText(/upload proof of funds document/i)
    await user.upload(input, PDF)

    expect(await screen.findByText(/how many documents/i)).toBeInTheDocument()
    expect(screen.queryByText(/^that file is too large\.$/i)).not.toBeInTheDocument()
  })

  it('413 file_too_large shows the file-size message', async () => {
    stubUploadError(413, 'file_too_large')
    const user = userEvent.setup({ delay: null })
    render(<VerificationStatus />)

    const input = await screen.findByLabelText(/upload proof of funds document/i)
    await user.upload(input, PDF)

    expect(await screen.findByText(/that file is too large/i)).toBeInTheDocument()
  })

  it('415 shows the allowed-types message', async () => {
    stubUploadError(415, null)
    const user = userEvent.setup({ delay: null })
    render(<VerificationStatus />)

    const input = await screen.findByLabelText(/upload proof of funds document/i)
    await user.upload(input, PDF)

    // The static helper copy ("PDF, PNG, or JPEG.") is on screen too, so this
    // pins the full sentence rather than the substring both share.
    expect(await screen.findByText(/only pdf, png, or jpeg documents are allowed/i)).toBeInTheDocument()
  })

  it('a document can be downloaded with the caller\'s credentials', async () => {
    const { fetchMock } = stubVerification({
      status: 'pending',
      documents: [
        {
          id: 5,
          original_filename: 'bank-statement.pdf',
          content_type: 'application/pdf',
          size_bytes: 2048,
          uploaded_at: '2026-07-20T00:00:00Z',
        },
      ],
    })
    const user = userEvent.setup({ delay: null })
    render(<VerificationStatus />)

    const downloadButton = await screen.findByRole('button', { name: /bank-statement\.pdf/i })
    await user.click(downloadButton)

    await waitFor(() => {
      const call = fetchMock.mock.calls.find((c) => String(c[0]) === '/api/verification/documents/5')
      expect(call).toBeDefined()
      const headers = (call?.[1]?.headers ?? {}) as Record<string, string>
      expect(headers.Authorization).toBe('Bearer a.b.c')
    })
  })
})
