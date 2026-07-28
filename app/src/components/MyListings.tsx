// M2 — the seller dashboard (spec H2; FR-8). Lists the caller's own listings
// with status; shows empty / loading / error states.
//
// Deliberately router-free: it is rendered standalone in its test, and pulling
// in navigation would couple a presentational list to a router context. The
// "List a business" action lives in the nav, which is sticky and on screen
// here — a second contained button would also break the design system's
// one-primary-CTA-per-screen rule.
import { useEffect, useState } from 'react'
import { Alert, Box, Card, Skeleton, Stack, Typography } from '@mui/material'
import StorefrontOutlined from '@mui/icons-material/StorefrontOutlined'
import { api } from '../lib/api'
import { SpotlightCard } from './SpotlightCard'
import { StatusChip } from './StatusChip'
import { formatPrice } from './DealActions'

// UI Pass 4 — the loading twin: 3 row-shaped skeleton cards matching this
// screen's actual row (headline + status chip).
function MyListingsSkeleton() {
  return (
    <Stack spacing={1.5} role="status" aria-label="Loading your listings">
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i} sx={{ p: 2.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
            <Skeleton height={22} width="55%" />
            <Skeleton width={70} height={24} />
          </Box>
        </Card>
      ))}
    </Stack>
  )
}

// UI Pass 3 (Part B1) — the empty-state spotlight card's points. The exact
// current heading string ("No listings yet — create your first one.") is
// preserved verbatim below (MyListings.test.tsx matches `/no listings yet/i`).
const EMPTY_STATE_POINTS = [
  'A new listing starts as a private draft. Nothing is visible to anyone until you submit it.',
  "Submitted listings go through review before they go live — we don't publish everything that arrives.",
  "Your company name, website and detailed financials stay behind the gate even once it's live.",
]

interface ListingRow {
  id: number
  headline: string
  status: string
  rejection_reason?: string | null
  // M12 (spec 012 F5). Null on every listing that has not closed; the price is
  // the accepted offer's, derived server-side.
  final_price?: string | null
  sold_at?: string | null
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

      {!error && rows === null && <MyListingsSkeleton />}

      {!error && rows?.length === 0 && (
        // Empty state as a designed state, not a bare sentence — it is the
        // first thing every new seller sees. No CTA on this card: the "List a
        // business" action already lives in the nav above, sticky and on
        // screen, and a second one here would break the one-primary-CTA rule.
        <SpotlightCard
          icon={<StorefrontOutlined sx={{ fontSize: 22, color: 'primary.main' }} />}
          eyebrow="GET STARTED"
          heading="No listings yet — create your first one."
          points={EMPTY_STATE_POINTS}
        >
          <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 420 }}>
            Use <strong>List a business</strong> above to start a draft.
          </Typography>
        </SpotlightCard>
      )}

      {!error && rows && rows.length > 0 && (
        <Stack spacing={1.5}>
          {rows.map((row) => (
            <Card
              key={row.id}
              sx={{
                p: 2.5,
                // Hover raises the shadow only (design_system_spec.md §5).
                '&:hover': { boxShadow: 3 },
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 2,
                }}
              >
                <Typography sx={{ fontWeight: 600, minWidth: 0, overflowWrap: 'anywhere' }}>
                  {row.headline}
                </Typography>
                <StatusChip status={row.status} />
              </Box>

              {/* A rejection is only useful if the seller can read why (spec
                  C6). Rendered as ordinary JSX text — React escapes it, and
                  this string is written by an admin and read by a seller, so
                  it is the one stored-XSS surface in the milestone. Never
                  dangerouslySetInnerHTML. */}
              {/* M12 — a sold listing shows what it sold for. The seller's own
                  dashboard is the only place this appears: `final_price` is
                  absent from `ListingPublic` by schema, so a sale price is
                  never anonymous data (spec 012 S11). */}
              {row.status === 'sold' && row.final_price && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Sold for {formatPrice(row.final_price)}
                </Typography>
              )}

              {row.status === 'rejected' && row.rejection_reason && (
                <Alert severity="warning" sx={{ mt: 2 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
                    Why this was rejected
                  </Typography>
                  <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>
                    {row.rejection_reason}
                  </Typography>
                </Alert>
              )}
            </Card>
          ))}
        </Stack>
      )}
    </Box>
  )
}
