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
//
// UI Pass 2 (highest-traffic component in the pass): padding, an identity
// tile, headline clamping, the shared `Metric`/`surfaceRecessed` primitives,
// a rebuilt locked strip, a dedicated price row, the `cardInteractive` hover
// lift + a focus-within ring, and a `ListingCardSkeleton` twin for
// `BrowseListings`'s loading state.
import { Box, Card, CardActionArea, Chip, Divider, Skeleton, Stack, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import LockOutlinedIcon from '@mui/icons-material/LockOutlined'
import { listingTypeLabel } from '../lib/listingTypes'
import { Metric } from './Metric'
import { WatchlistButton } from './WatchlistButton'
import { badge, brand, brandTint, cardInteractive, elevation, metricLabel, metricValue, neutral, surfaceRecessed } from '../theme'

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

// A fixed palette of gradient pairs, all drawn from existing theme tokens
// (brand blue, slate shades, badge fills) — never `accent`/orange, which is
// brand-reserved (theme.ts's `accent` token comment). The pick is deterministic
// on the listing id, so the same listing always gets the same tile.
const TILE_GRADIENTS: readonly [string, string][] = [
  [brand.main, brand.dark],
  [brand.dark, brand.darker],
  [neutral[500], neutral[700]],
  [neutral[600], neutral[900]],
  [badge.premium.fg, neutral[900]],
  [badge.verified.fg, neutral[800]],
]

// A small 48px identity tile beside the type chip — a stand-in for the
// (locked) company identity, never the identity itself: it renders only the
// business type's first letter and a deterministic colour, nothing from the
// listing's private fields.
//
// Exported so `ListingDetail` reuses the exact same tile/palette rather than a
// second implementation that could drift from this one.
export function IdentityTile({ id, type }: { id: number; type: string }) {
  const [from, to] = TILE_GRADIENTS[Math.abs(id) % TILE_GRADIENTS.length]
  const letter = listingTypeLabel(type).charAt(0).toUpperCase() || '?'
  return (
    <Box
      aria-hidden
      sx={{
        width: 48,
        height: 48,
        borderRadius: 1.5,
        flexShrink: 0,
        background: `linear-gradient(135deg, ${from}, ${to})`,
        color: '#fff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontWeight: 700,
        fontSize: '1.25rem',
      }}
    >
      {letter}
    </Box>
  )
}

// The gate, made visible — rebuilt in Pass 2 (surfaceRecessed + a lock icon +
// blurred placeholder bars) but the caption copy is unchanged verbatim.
function LockedStrip() {
  return (
    <Box sx={{ ...surfaceRecessed, p: 1.5, mt: 'auto' }}>
      <Stack direction="row" spacing={1.5} alignItems="flex-start">
        <Box
          sx={{
            width: 24,
            height: 24,
            borderRadius: '50%',
            bgcolor: brandTint,
            color: 'primary.main',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <LockOutlinedIcon sx={{ fontSize: 14 }} />
        </Box>
        <Stack spacing={0.75} sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="caption" color="text.secondary">
            Company name and financials are locked until the NDA is signed
          </Typography>
          {/* Redacted-field placeholders — decorative only. */}
          <Box aria-hidden sx={{ height: 8, borderRadius: 1, bgcolor: neutral[100], filter: 'blur(5px)', opacity: 0.7, width: '75%' }} />
          <Box aria-hidden sx={{ height: 8, borderRadius: 1, bgcolor: neutral[100], filter: 'blur(5px)', opacity: 0.7, width: '45%' }} />
        </Stack>
      </Stack>
    </Box>
  )
}

export function ListingCard({ listing }: { listing: PublicListing }) {
  return (
    // M9 — the watchlist heart sits on top of the card but must not be a DOM
    // descendant of CardActionArea (a ButtonBase acting as the whole card's
    // router link): a nested interactive button inside it is invalid nesting
    // and would fight the card's own click-to-navigate. Positioned as a
    // sibling instead, absolutely placed over the relatively-positioned Box.
    <Box sx={{ position: 'relative' }}>
      <Card
        sx={{
          height: '100%',
          ...cardInteractive,
          '&:focus-within': { boxShadow: elevation.ring },
        }}
      >
        <CardActionArea
          component={RouterLink}
          to={`/browse/${listing.id}`}
          sx={{ height: '100%', p: 3, display: 'block', textAlign: 'left' }}
        >
          <Stack spacing={1.5} sx={{ height: '100%' }}>
            <Stack direction="row" spacing={1.5} alignItems="center">
              <IdentityTile id={listing.id} type={listing.type} />
              <Chip label={listingTypeLabel(listing.type)} size="small" />
            </Stack>

            <Typography
              variant="h6"
              component="h3"
              sx={{
                overflowWrap: 'anywhere',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }}
            >
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
                ...surfaceRecessed,
                p: 1.5,
                display: 'grid',
                gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
                gap: 1.5,
              }}
            >
              <Metric label="MRR" value={money(listing.mrr)} />
              <Metric label="TTM profit" value={money(listing.ttm_profit)} />
              <Metric label="Customers" value={listing.customers.toLocaleString('en-US')} />
            </Box>

            <LockedStrip />

            <Divider />
            <Stack direction="row" alignItems="baseline" justifyContent="space-between" sx={{ gap: 1 }}>
              <Typography component="div" sx={metricLabel}>
                Asking price
              </Typography>
              <Typography component="div" sx={{ ...metricValue, fontSize: '1.25rem' }}>
                {money(listing.asking_price)}
              </Typography>
            </Stack>
          </Stack>
        </CardActionArea>
      </Card>
      {/* Sibling of CardActionArea, not a child — see the comment above. */}
      <Box sx={{ position: 'absolute', top: 12, right: 12, zIndex: 1 }}>
        <WatchlistButton listingId={listing.id} />
      </Box>
    </Box>
  )
}

// The loading twin — `BrowseListings` renders 6 of these instead of a
// spinner, in roughly the same shape as the loaded card above so the grid
// doesn't visibly reflow once data arrives.
export function ListingCardSkeleton() {
  return (
    <Card sx={{ height: '100%', p: 3 }}>
      <Stack spacing={1.5} sx={{ height: '100%' }}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Skeleton variant="circular" width={48} height={48} />
          <Skeleton variant="rounded" width={64} height={24} />
        </Stack>
        <Skeleton variant="rounded" height={20} width="90%" />
        <Skeleton variant="rounded" height={16} width="65%" />
        <Box
          sx={{
            ...surfaceRecessed,
            p: 1.5,
            display: 'grid',
            gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
            gap: 1.5,
          }}
        >
          <Skeleton variant="rounded" height={32} />
          <Skeleton variant="rounded" height={32} />
          <Skeleton variant="rounded" height={32} />
        </Box>
        <Skeleton variant="rounded" height={56} sx={{ mt: 'auto' }} />
        <Divider />
        <Stack direction="row" justifyContent="space-between">
          <Skeleton variant="rounded" width={80} height={16} />
          <Skeleton variant="rounded" width={90} height={24} />
        </Stack>
      </Stack>
    </Card>
  )
}
