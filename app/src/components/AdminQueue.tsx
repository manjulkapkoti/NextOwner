// M3 — the admin curation queue (spec F1-F3).
//
// Curation is the product's quality promise, so this screen's job is to make a
// decision easy and a mistake hard: the private company detail is on screen (an
// admin cannot judge what they cannot see), and rejecting requires typing a
// reason the seller will actually read.
import { useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Link as MuiLink,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { ApiError, api } from '../lib/api'
import { StatusChip } from './StatusChip'
import { tabularNums } from '../theme'

interface QueueRow {
  id: number
  headline: string
  type: string
  asking_price: string
  status: string
  created_at: string
  company_name: string | null
  website_url: string | null
}

function formatPrice(value: string): string {
  const n = Number(value)
  return Number.isFinite(n) ? n.toLocaleString('en-US', { maximumFractionDigits: 0 }) : value
}

export function AdminQueue() {
  const [rows, setRows] = useState<QueueRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  // The listing being rejected, plus its reason — a dialog rather than an
  // inline field, so a rejection is a deliberate act.
  const [rejecting, setRejecting] = useState<QueueRow | null>(null)
  const [reason, setReason] = useState('')
  const [reasonError, setReasonError] = useState<string | null>(null)

  async function load() {
    try {
      setRows(await api('/admin/listings?status=pending_review'))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load the queue.')
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function decide(row: QueueRow, action: 'approve' | 'reject', body?: object) {
    setBusyId(row.id)
    setError(null)
    try {
      await api(`/listings/${row.id}/${action}`, {
        method: 'POST',
        ...(body ? { body: JSON.stringify(body) } : {}),
      })
      // Refetch rather than mutating locally: the server owns the status, and
      // another admin may have decided this listing in the meantime.
      await load()
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
      // Blocked here rather than sent — the server would 422 (spec C3), but a
      // round trip to learn you left a box empty is a poor way to find out.
      setReasonError('A reason is required — the seller sees this.')
      return
    }
    setReasonError(null)
    if (rejecting) void decide(rejecting, 'reject', { reason: reason.trim() })
  }

  return (
    <Box>
      <Typography variant="h4" component="h1" sx={{ mb: 1 }}>
        Curation queue
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Listings waiting for review. Approving publishes to the marketplace; rejecting returns it
        to the seller with your reason.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {rows === null && !error && (
        <Stack alignItems="center" sx={{ py: 8 }}>
          <CircularProgress aria-label="loading the queue" />
        </Stack>
      )}

      {rows?.length === 0 && (
        <Card sx={{ p: { xs: 4, sm: 6 }, textAlign: 'center' }}>
          <Typography variant="h6">Nothing waiting for review</Typography>
          <Typography variant="body2" color="text.secondary">
            Submitted listings appear here.
          </Typography>
        </Card>
      )}

      <Stack spacing={1.5}>
        {rows?.map((row) => (
          <Card key={row.id} sx={{ p: 2.5 }}>
            <Stack
              direction={{ xs: 'column', sm: 'row' }}
              justifyContent="space-between"
              alignItems={{ xs: 'flex-start', sm: 'center' }}
              gap={2}
            >
              <Box sx={{ minWidth: 0 }}>
                <Stack direction="row" alignItems="center" gap={1} sx={{ mb: 0.5 }}>
                  <Typography sx={{ fontWeight: 600, overflowWrap: 'anywhere' }}>
                    {row.headline}
                  </Typography>
                  <StatusChip status={row.status} />
                </Stack>
                <Typography variant="body2" color="text.secondary" sx={{ ...tabularNums }}>
                  {row.type} · ${formatPrice(row.asking_price)}
                </Typography>
                {/* Private detail — visible because an admin is authorised to
                    see it and cannot curate blind (spec A5). */}
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  {row.company_name}
                  {row.website_url && (
                    <>
                      {' · '}
                      <MuiLink href={row.website_url} target="_blank" rel="noopener noreferrer">
                        {row.website_url}
                      </MuiLink>
                    </>
                  )}
                </Typography>
              </Box>

              <Stack direction="row" gap={1} sx={{ flexShrink: 0 }}>
                <Button
                  variant="contained"
                  disabled={busyId === row.id}
                  onClick={() => void decide(row, 'approve')}
                >
                  Approve
                </Button>
                <Button
                  color="inherit"
                  disabled={busyId === row.id}
                  sx={{ color: 'text.secondary' }}
                  onClick={() => {
                    setRejecting(row)
                    setReason('')
                    setReasonError(null)
                  }}
                >
                  Reject
                </Button>
              </Stack>
            </Stack>
          </Card>
        ))}
      </Stack>

      <Dialog open={rejecting !== null} onClose={() => setRejecting(null)} fullWidth maxWidth="sm">
        <DialogTitle>Reject “{rejecting?.headline}”</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            The seller sees this, so say what needs to change.
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
            Confirm reject
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
