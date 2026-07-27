// M5 — the seller's per-listing access-request queue (spec 005 J4, FR-14).
//
// This is the screen where the product's positioning stops being a slogan: the
// seller reads who is asking and *chooses* who carries the business forward.
// So it shows enough to decide — budget, sector, experience — and nothing more.
//
// **No verification badge** (spec 005 § Decisions D5). M10 owns buyer
// verification; a placeholder here would be an unenforced flag, which
// `security.md` §7 calls decoration. M10's fold-in already covers adding it.
//
// **No buyer email**, because the API does not send one (G3): the seller gets a
// profile, and chat (M6) is the channel once they have decided.
//
// UI Pass 4: the loading state is a row-shaped skeleton, the empty state uses
// the shared `EmptyState`, and each row uses the shared `PersonRow` (with the
// dense-queue status dot opted in) instead of a hand-rolled Card/Stack tree.
import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  Skeleton,
  Stack,
  Typography,
} from '@mui/material'
import { api } from '../lib/api'
import { EmptyState } from './EmptyState'
import { PersonRow } from './PersonRow'
import { StatusChip } from './StatusChip'
import { blueTint } from '../theme'

interface BuyerProfile {
  display_name: string | null
  budget: string | number | null
  // The API sends a string today; an array is tolerated so the shape can grow
  // into structured sectors without this component becoming the blocker.
  target_industries: string | string[] | null
  experience: string | null
}

interface QueueRow {
  id: number
  listing_id: number
  status: string
  created_at: string
  decided_at: string | null
  buyer: BuyerProfile
}

interface Props {
  listingId: number
}

function formatBudget(budget: string | number | null): string | null {
  if (budget === null || budget === '') return null
  const value = Number(budget)
  return Number.isFinite(value) ? value.toLocaleString('en-US') : String(budget)
}

function formatIndustries(industries: string | string[] | null): string | null {
  if (!industries) return null
  return Array.isArray(industries) ? industries.join(', ') : industries
}

function AccessRequestQueueSkeleton() {
  return (
    <Stack spacing={2} role="status" aria-label="Loading access requests">
      {Array.from({ length: 2 }).map((_, i) => (
        <Card key={i} variant="outlined">
          <CardContent>
            <Stack direction="row" spacing={2} alignItems="flex-start">
              <Skeleton variant="circular" width={40} height={40} />
              <Box sx={{ flex: 1 }}>
                <Skeleton height={22} width="40%" sx={{ mb: 1 }} />
                <Skeleton height={14} width="30%" sx={{ mb: 0.5 }} />
                <Skeleton height={14} width="60%" />
                <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                  <Skeleton width={90} height={32} />
                  <Skeleton width={70} height={32} />
                </Stack>
              </Box>
            </Stack>
          </CardContent>
        </Card>
      ))}
    </Stack>
  )
}

export function AccessRequestQueue({ listingId }: Props) {
  const [rows, setRows] = useState<QueueRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(async () => {
    try {
      setRows((await api(`/my/listings/${listingId}/access-requests`)) as QueueRow[])
    } catch {
      setError('We could not load the requests for this listing.')
    }
  }, [listingId])

  useEffect(() => {
    void load()
  }, [load])

  async function decide(requestId: number, action: 'approve' | 'deny' | 'revoke') {
    setBusyId(requestId)
    setError(null)
    try {
      await api(`/access-requests/${requestId}/${action}`, { method: 'POST' })
      // Re-read from the server rather than patching local state: the row's new
      // status is the server's to decide, and a client guess that drifted would
      // show the seller a decision that did not happen.
      await load()
    } catch {
      setError('That decision could not be saved. Please try again.')
    } finally {
      setBusyId(null)
    }
  }

  if (error && rows === null) {
    return (
      <Alert severity="error" role="alert">
        {error}
      </Alert>
    )
  }

  if (rows === null) {
    return <AccessRequestQueueSkeleton />
  }

  if (rows.length === 0) {
    return <EmptyState message="No one has asked for access to this listing yet." />
  }

  return (
    <Stack spacing={2}>
      {error && (
        <Alert severity="error" role="alert">
          {error}
        </Alert>
      )}
      {rows.map((row) => {
        const budget = formatBudget(row.buyer.budget)
        const industries = formatIndustries(row.buyer.target_industries)
        const name = row.buyer.display_name ?? 'Unnamed buyer'
        return (
          <PersonRow
            key={row.id}
            avatar={
              <Avatar sx={{ bgcolor: blueTint.wash, color: blueTint.onWash, fontWeight: 700 }}>
                {name.charAt(0).toUpperCase()}
              </Avatar>
            }
            title={<Typography variant="subtitle1">{name}</Typography>}
            meta={
              <>
                {budget && (
                  <Typography variant="body2" color="text.secondary">
                    Budget: {budget}
                  </Typography>
                )}
                {industries && (
                  <Typography variant="body2" color="text.secondary">
                    {industries}
                  </Typography>
                )}
                {row.buyer.experience && (
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    {row.buyer.experience}
                  </Typography>
                )}
              </>
            }
            chip={<StatusChip status={row.status} showDot />}
            actions={
              // The actions mirror the server's state machine exactly: approve
              // and deny are legal only from `requested`, revoke only from
              // `approved`. Offering a button the server would 409 teaches the
              // seller to distrust the screen.
              <>
                {row.status === 'requested' && (
                  <>
                    <Button
                      variant="contained"
                      size="small"
                      disabled={busyId === row.id}
                      onClick={() => decide(row.id, 'approve')}
                    >
                      Approve
                    </Button>
                    <Button
                      variant="outlined"
                      size="small"
                      disabled={busyId === row.id}
                      onClick={() => decide(row.id, 'deny')}
                    >
                      Deny
                    </Button>
                  </>
                )}
                {row.status === 'approved' && (
                  <Button
                    variant="outlined"
                    color="warning"
                    size="small"
                    disabled={busyId === row.id}
                    onClick={() => decide(row.id, 'revoke')}
                  >
                    Revoke
                  </Button>
                )}
              </>
            }
          />
        )
      })}
    </Stack>
  )
}
