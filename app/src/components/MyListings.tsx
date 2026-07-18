// M2 — the seller dashboard (spec H2; FR-8). Lists the caller's own listings
// with status; shows empty / loading / error states.
//
// Deliberately router-free: it is rendered standalone in its test, and pulling
// in navigation would couple a presentational list to a router context. The
// "List a business" action lives in the nav, which is sticky and on screen
// here — a second contained button would also break the design system's
// one-primary-CTA-per-screen rule.
import { useEffect, useState } from 'react'
import { Alert, Box, Card, CircularProgress, Stack, Typography } from '@mui/material'
import { api } from '../lib/api'
import { StatusChip } from './StatusChip'

interface ListingRow {
  id: number
  headline: string
  status: string
}

export function MyListings() {
  const [rows, setRows] = useState<ListingRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api('/my/listings')
      .then((data) => setRows(data))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  return (
    <Box>
      <Stack
        direction="row"
        alignItems="baseline"
        justifyContent="space-between"
        sx={{ mb: 3, gap: 2 }}
      >
        <Typography variant="h4" component="h1">
          Your listings
        </Typography>
        {rows && rows.length > 0 && (
          <Typography variant="body2" color="text.secondary">
            {rows.length} {rows.length === 1 ? 'listing' : 'listings'}
          </Typography>
        )}
      </Stack>

      {error && <Alert severity="error">Couldn't load your listings: {error}</Alert>}

      {!error && rows === null && (
        <Stack alignItems="center" sx={{ py: 8 }}>
          <CircularProgress aria-label="loading your listings" />
        </Stack>
      )}

      {!error && rows?.length === 0 && (
        // Empty state as a designed state, not a bare sentence — it is the
        // first thing every new seller sees.
        <Card sx={{ p: { xs: 4, sm: 6 }, textAlign: 'center' }}>
          <Typography variant="h6" sx={{ mb: 1 }}>
            No listings yet — create your first one.
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 420, mx: 'auto' }}>
            Use <strong>List a business</strong> above to start a draft. Nothing is public until
            you submit it and it passes review.
          </Typography>
        </Card>
      )}

      {!error && rows && rows.length > 0 && (
        <Stack spacing={1.5}>
          {rows.map((row) => (
            <Card
              key={row.id}
              sx={{
                p: 2.5,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 2,
                // Hover raises the shadow only (design_system_spec.md §5).
                '&:hover': { boxShadow: 3 },
              }}
            >
              <Typography sx={{ fontWeight: 600, minWidth: 0, overflowWrap: 'anywhere' }}>
                {row.headline}
              </Typography>
              <StatusChip status={row.status} />
            </Card>
          ))}
        </Stack>
      )}
    </Box>
  )
}
