// M4 — the anonymous listing card (spec 004 criterion F1; FR-6).
//
// The card is where the anonymity promise is kept on the client. The server
// already makes a leak impossible by schema, but this component may one day be
// handed a fuller object (a seller preview, an admin surface), so it renders
// from an explicit field list and never spreads the listing into the DOM.
//
// The locked strip is not decoration: a buyer has to understand there IS
// something behind the NDA, or the gate reads as missing data rather than as
// the product's core mechanic.
import { Box, Card, CardActionArea, Chip, Stack, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import { listingTypeLabel } from '../lib/listingTypes'

export interface PublicListing {
  id: number
  type: string
  headline: string
  description: string
  asking_price: string
  ttm_revenue: string
  ttm_profit: string
  mrr: string
  churn_pct: string
  customers: number
  published_at: string | null
}

// Money arrives as an exact decimal string (the server never sends a float).
// Parsing to Number here is for *display* only — no arithmetic happens on it.
function money(value: string): string {
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  })
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 600 }}>{value}</Typography>
    </Box>
  )
}

export function ListingCard({ listing }: { listing: PublicListing }) {
  return (
    <Card sx={{ height: '100%', '&:hover': { boxShadow: 3 } }}>
      <CardActionArea
        component={RouterLink}
        to={`/browse/${listing.id}`}
        sx={{ height: '100%', p: 2.5, display: 'block', textAlign: 'left' }}
      >
        <Stack spacing={1.5} sx={{ height: '100%' }}>
          <Chip
            label={listingTypeLabel(listing.type)}
            size="small"
            sx={{ alignSelf: 'flex-start' }}
          />

          <Typography variant="h6" component="h3" sx={{ overflowWrap: 'anywhere' }}>
            {listing.headline}
          </Typography>

          <Typography
            variant="body2"
            color="text.secondary"
            sx={{
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {listing.description}
          </Typography>

          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
              gap: 1.5,
              pt: 0.5,
            }}
          >
            <Metric label="MRR" value={money(listing.mrr)} />
            <Metric label="TTM profit" value={money(listing.ttm_profit)} />
            <Metric label="Customers" value={listing.customers.toLocaleString('en-US')} />
          </Box>

          {/* The gate, made visible. M5 turns this into a real request-access
              action; until then it explains rather than invites. */}
          <Box
            sx={{
              mt: 'auto',
              px: 1.5,
              py: 1,
              borderRadius: 1,
              bgcolor: 'action.hover',
              border: '1px dashed',
              borderColor: 'divider',
            }}
          >
            <Typography variant="caption" color="text.secondary">
              Company name and financials are locked until the NDA is signed
            </Typography>
          </Box>

          <Stack direction="row" alignItems="baseline" justifyContent="space-between" sx={{ gap: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Asking price
            </Typography>
            <Typography variant="h6" component="p">
              {money(listing.asking_price)}
            </Typography>
          </Stack>
        </Stack>
      </CardActionArea>
    </Card>
  )
}
