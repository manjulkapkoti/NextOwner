// M10 — the buyer's own verification page (spec 010 § Frontend), reachable at
// /verification. This is the codebase's Persona mock's buyer-facing half:
// upload proof of funds, see what the seller sees (D7's badge, mirrored).
//
// Mirrors Watchlist.tsx / AdminQueue.tsx's empty/loading/error triad. The
// upload form is hidden — not just disabled — once `verified` (D3): the
// server 409s `already_verified` on that path, and the plan is explicit that
// the button should be "hidden/disabled when already verified, not just left
// to fail," so a verified buyer never gets to click into a 409 at all.
import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { Alert, Box, Button, Card, Skeleton, Stack, Typography } from '@mui/material'
import { observer } from 'mobx-react-lite'
import { ApiError } from '../lib/api'
import { downloadFile } from '../lib/download'
import { verificationStore, type VerificationDocument } from '../stores/verificationStore'
import { StatusChip } from './StatusChip'
import { surfaceRecessed } from '../theme'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// UI Pass 4-style loading twin: a status-card shape plus an upload-card shape,
// matching this screen's actual two-block layout.
function VerificationStatusSkeleton() {
  return (
    <Stack spacing={2} role="status" aria-label="Loading your verification status">
      <Card sx={{ p: 3 }}>
        <Skeleton height={24} width="30%" sx={{ mb: 1 }} />
        <Skeleton height={16} width="45%" />
      </Card>
      <Card sx={{ p: 3 }}>
        <Skeleton height={20} width="40%" sx={{ mb: 1.5 }} />
        <Skeleton height={36} width={140} />
      </Card>
    </Stack>
  )
}

// The 413/415/409/422 branches this uploader can hit (docs/error_handling.md
// §3): each gets a specific message, not a generic failure toast — the plan's
// explicit instruction, since "file too large" and "too many documents" are
// different problems with different next steps for the buyer.
function uploadErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 409) return "You're already verified — no need to resubmit."
    if (err.status === 415) return 'Only PDF, PNG, or JPEG documents are allowed.'
    if (err.status === 413) {
      return err.code === 'upload_quota_exceeded'
        ? "You've reached the limit on how many documents (or how much total data) you can upload."
        : 'That file is too large.'
    }
    if (err.status === 422) return 'Choose a file to upload.'
  }
  return 'That upload did not go through. Please try again.'
}

export const VerificationStatus = observer(function VerificationStatus() {
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    void verificationStore.load()
  }, [])

  async function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadError(null)
    setUploading(true)
    try {
      await verificationStore.upload(file)
    } catch (err) {
      setUploadError(uploadErrorMessage(err))
    } finally {
      setUploading(false)
      // Reset so re-selecting the same file (e.g. after fixing nothing, just
      // retrying) still fires onChange.
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleDownload(doc: VerificationDocument) {
    setDownloadError(null)
    try {
      await downloadFile(`/verification/documents/${doc.id}`, doc.original_filename)
    } catch {
      setDownloadError('That document could not be downloaded just now.')
    }
  }

  if (verificationStore.error) {
    return (
      <Alert severity="error" role="alert">
        {verificationStore.error}
      </Alert>
    )
  }

  if (verificationStore.loading && !verificationStore.loaded) {
    return <VerificationStatusSkeleton />
  }

  const { status, reviewedAt, reason, documents } = verificationStore
  // D3 mirrored client-side: the button is hidden once verified rather than
  // left to fail — the server's 409 `already_verified` is still the real
  // boundary if this ever drifts.
  const canUpload = status !== 'verified'

  return (
    <Box>
      <Typography variant="h4" component="h1" sx={{ mb: 1 }}>
        Buyer verification
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Upload proof of funds so sellers can see you&apos;re a serious buyer. An admin reviews
        every submission by hand.
      </Typography>

      <Card sx={{ p: 3, mb: 3 }}>
        <Stack direction="row" alignItems="center" spacing={1.5}>
          <Typography variant="subtitle1">Status</Typography>
          <StatusChip status={status} />
        </Stack>
        {reviewedAt && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Last reviewed {new Date(reviewedAt).toLocaleDateString()}
          </Typography>
        )}
        {status === 'rejected' && reason && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            {reason}
          </Alert>
        )}
      </Card>

      {canUpload ? (
        <Card sx={{ p: 3, mb: 3 }}>
          <Typography variant="subtitle1" sx={{ mb: 0.5 }}>
            {status === 'rejected' ? 'Resubmit proof of funds' : 'Upload proof of funds'}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            PDF, PNG, or JPEG.
          </Typography>
          {uploadError && (
            <Alert severity="error" sx={{ mb: 2 }} role="alert">
              {uploadError}
            </Alert>
          )}
          <Button variant="contained" component="label" disabled={uploading}>
            {uploading ? 'Uploading…' : 'Choose file'}
            <input
              ref={fileInputRef}
              type="file"
              hidden
              aria-label="Upload proof of funds document"
              accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
              onChange={(e) => void handleFile(e)}
            />
          </Button>
        </Card>
      ) : (
        // The upload form is absent, not disabled-and-visible (plan.md §
        // Frontend) — a verified buyer sees why there's nothing to do here
        // instead of a greyed-out control with no explanation.
        <Alert severity="success" sx={{ mb: 3 }}>
          You&apos;re verified. An admin would need to revoke this before you could submit a new
          document.
        </Alert>
      )}

      <Typography variant="subtitle1" sx={{ mb: 1 }}>
        Documents
      </Typography>
      {downloadError && (
        <Alert severity="error" sx={{ mb: 2 }} role="alert">
          {downloadError}
        </Alert>
      )}
      {documents.length === 0 ? (
        <Box sx={{ ...surfaceRecessed, p: 2 }}>
          <Typography variant="body2" color="text.secondary">
            No documents submitted yet.
          </Typography>
        </Box>
      ) : (
        <Stack spacing={1}>
          {documents.map((doc) => (
            <Button
              key={doc.id}
              variant="outlined"
              size="small"
              sx={{ alignSelf: 'flex-start' }}
              onClick={() => void handleDownload(doc)}
            >
              {doc.original_filename} · {formatBytes(doc.size_bytes)}
            </Button>
          ))}
        </Stack>
      )}
    </Box>
  )
})
