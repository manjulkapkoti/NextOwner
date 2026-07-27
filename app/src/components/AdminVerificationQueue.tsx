// M10 — the admin buyer-verification queue (spec 010 § Frontend), the
// demand-side sibling of `AdminQueue.tsx` (M3's listing curation). Mirrors
// that screen's structure closely: a filtered list, a private-detail block an
// admin is authorised to see, and a reject dialog that requires a reason.
//
// A status filter (Pending/Verified/Rejected) is not merely a listing
// convenience: `reject` doubles as *deny* (from `pending`) and *revoke* (from
// `verified`, D1's story 4), so an admin needs a way to reach an
// already-verified buyer to revoke them — the same reasoning the backend's
// `?status=` query documents (spec 010 D13, V15). `?status=unverified` is
// deliberately never requested here (S12 — the server 422s it by schema).
import { useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Skeleton,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import { ApiError, api } from '../lib/api'
import { downloadFile } from '../lib/download'
import { EmptyState } from './EmptyState'
import { StatusChip } from './StatusChip'
import { surfaceRecessed, tabularNums } from '../theme'

interface QueueDocument {
  id: number
  original_filename: string
  content_type: string
  size_bytes: number
  uploaded_at: string
}

interface QueueRow {
  user_id: number
  email: string
  display_name: string | null
  budget: string | number | null
  target_industries: string | string[] | null
  experience: string | null
  verification_status: string
  documents: QueueDocument[]
}

type Filter = 'pending' | 'verified' | 'rejected'

function formatBudget(budget: string | number | null): string | null {
  if (budget === null || budget === '') return null
  const value = Number(budget)
  return Number.isFinite(value) ? value.toLocaleString('en-US') : String(budget)
}

function formatIndustries(industries: string | string[] | null): string | null {
  if (!industries) return null
  return Array.isArray(industries) ? industries.join(', ') : industries
}

function AdminVerificationQueueSkeleton() {
  return (
    <Stack spacing={1.5} role="status" aria-label="Loading the verification queue">
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i} sx={{ p: 2.5 }}>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            justifyContent="space-between"
            alignItems={{ xs: 'flex-start', sm: 'center' }}
            gap={2}
            sx={{ width: '100%' }}
          >
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Skeleton height={22} width="50%" sx={{ mb: 1 }} />
              <Skeleton height={16} width="35%" sx={{ mb: 1 }} />
              <Skeleton height={40} width="80%" />
            </Box>
            <Stack direction="row" gap={1} sx={{ flexShrink: 0 }}>
              <Skeleton width={100} height={36} />
              <Skeleton width={80} height={36} />
            </Stack>
          </Stack>
        </Card>
      ))}
    </Stack>
  )
}

export function AdminVerificationQueue() {
  const [filter, setFilter] = useState<Filter>('pending')
  const [rows, setRows] = useState<QueueRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  // The buyer being rejected/revoked, plus the reason — a dialog rather than
  // an inline field, mirroring AdminQueue.tsx's own reject flow (M3).
  const [rejecting, setRejecting] = useState<QueueRow | null>(null)
  const [reason, setReason] = useState('')
  const [reasonError, setReasonError] = useState<string | null>(null)

  async function load(status: Filter) {
    try {
      setRows((await api(`/admin/verifications?status=${status}`)) as QueueRow[])
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load the queue.')
    }
  }

  useEffect(() => {
    setRows(null)
    setError(null)
    void load(filter)
  }, [filter])

  async function decide(row: QueueRow, action: 'approve' | 'reject', body?: object) {
    setBusyId(row.user_id)
    setError(null)
    try {
      await api(`/admin/verifications/${row.user_id}/${action}`, {
        method: 'POST',
        ...(body ? { body: JSON.stringify(body) } : {}),
      })
      // Refetch rather than mutating locally: the server owns the status, and
      // another admin may have decided this buyer in the meantime.
      await load(filter)
      setRejecting(null)
      setReason('')
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'That did not go through.')
    } finally {
      setBusyId(null)
    }
  }

  function confirmReject() {
    if (!reason.trim()) {
      // Blocked here rather than sent — the server would 422 (X2), but a round
      // trip to learn you left a box empty is a poor way to find out.
      setReasonError('A reason is required — the buyer sees this.')
      return
    }
    setReasonError(null)
    if (rejecting) void decide(rejecting, 'reject', { reason: reason.trim() })
  }

  async function handleDownload(doc: QueueDocument) {
    setDownloadError(null)
    try {
      await downloadFile(`/verification/documents/${doc.id}`, doc.original_filename)
    } catch {
      setDownloadError('That document could not be downloaded just now.')
    }
  }

  const isRevoke = rejecting?.verification_status === 'verified'

  return (
    <Box>
      <Typography variant="h4" component="h1" sx={{ mb: 1 }}>
        Buyer verification queue
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Review proof-of-funds submissions. Approving grants the verified badge; rejecting denies
        it — or, for an already-verified buyer, revokes it — with your reason.
      </Typography>

      <ToggleButtonGroup
        value={filter}
        exclusive
        size="small"
        onChange={(_, value: Filter | null) => value && setFilter(value)}
        aria-label="Filter by status"
        sx={{ mb: 3 }}
      >
        <ToggleButton value="pending">Pending</ToggleButton>
        <ToggleButton value="verified">Verified</ToggleButton>
        <ToggleButton value="rejected">Rejected</ToggleButton>
      </ToggleButtonGroup>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} role="alert">
          {error}
        </Alert>
      )}
      {downloadError && (
        <Alert severity="error" sx={{ mb: 2 }} role="alert">
          {downloadError}
        </Alert>
      )}

      {rows === null && !error && <AdminVerificationQueueSkeleton />}

      {rows?.length === 0 && <EmptyState message={`No ${filter} submissions right now.`} />}

      <Stack spacing={1.5}>
        {rows?.map((row) => {
          const budget = formatBudget(row.budget)
          const industries = formatIndustries(row.target_industries)
          const name = row.display_name ?? row.email

          return (
            <Card key={row.user_id} sx={{ p: 2.5 }}>
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                justifyContent="space-between"
                alignItems={{ xs: 'flex-start', sm: 'flex-start' }}
                gap={2}
              >
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Stack direction="row" alignItems="center" gap={1} sx={{ mb: 0.5 }}>
                    <Typography sx={{ fontWeight: 600, overflowWrap: 'anywhere' }}>
                      {name}
                    </Typography>
                    <StatusChip status={row.verification_status} />
                  </Stack>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                    {row.email}
                  </Typography>
                  {budget && (
                    <Typography variant="body2" color="text.secondary" sx={{ ...tabularNums }}>
                      Budget: {budget}
                    </Typography>
                  )}
                  {industries && (
                    <Typography variant="body2" color="text.secondary">
                      {industries}
                    </Typography>
                  )}
                  {row.experience && (
                    <Typography variant="body2" sx={{ mt: 0.5 }}>
                      {row.experience}
                    </Typography>
                  )}

                  {row.documents.length > 0 && (
                    <Box sx={{ ...surfaceRecessed, mt: 1.5, p: 1.25 }}>
                      <Typography variant="overline" sx={{ display: 'block', mb: 0.5 }}>
                        Documents
                      </Typography>
                      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                        {row.documents.map((doc) => (
                          <Button
                            key={doc.id}
                            size="small"
                            variant="outlined"
                            onClick={() => void handleDownload(doc)}
                          >
                            {doc.original_filename}
                          </Button>
                        ))}
                      </Stack>
                    </Box>
                  )}
                </Box>

                <Stack direction="row" gap={1} sx={{ flexShrink: 0 }}>
                  {/* Approve is only offered on a pending row — the server
                      409s from anything else (X3), so an Approve button
                      elsewhere would just teach the admin to distrust it. */}
                  {row.verification_status === 'pending' && (
                    <Button
                      variant="contained"
                      disabled={busyId === row.user_id}
                      onClick={() => void decide(row, 'approve')}
                    >
                      Approve
                    </Button>
                  )}
                  {/* Reject is offered on pending (deny) and verified
                      (revoke) rows — the two legal from-states (D1) — but not
                      on an already-rejected row (X4: 409 from `rejected`). */}
                  {row.verification_status !== 'rejected' && (
                    <Button
                      color="inherit"
                      disabled={busyId === row.user_id}
                      sx={{ color: 'text.secondary' }}
                      onClick={() => {
                        setRejecting(row)
                        setReason('')
                        setReasonError(null)
                      }}
                    >
                      {row.verification_status === 'verified' ? 'Revoke' : 'Reject'}
                    </Button>
                  )}
                </Stack>
              </Stack>
            </Card>
          )
        })}
      </Stack>

      <Dialog open={rejecting !== null} onClose={() => setRejecting(null)} fullWidth maxWidth="sm">
        <DialogTitle>
          {isRevoke ? 'Revoke' : 'Reject'} “{rejecting?.display_name ?? rejecting?.email}”
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            The buyer sees this, so say what needs to change.
          </Typography>
          <TextField
            label="Reason"
            fullWidth
            multiline
            minRows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            error={Boolean(reasonError)}
            helperText={reasonError}
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button color="inherit" onClick={() => setRejecting(null)} sx={{ color: 'text.secondary' }}>
            Cancel
          </Button>
          <Button variant="contained" color="error" onClick={confirmReject}>
            Confirm {isRevoke ? 'revoke' : 'reject'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
