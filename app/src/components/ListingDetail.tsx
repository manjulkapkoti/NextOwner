// M4 — the public listing detail at /browse/:id (spec 004 C1-C4).
//
// Same anonymity rules as the card: this renders only fields the public schema
// carries. A non-live or missing listing is a 404 from the server and shows the
// same "not available" message here — the client must not become the existence
// oracle the API deliberately isn't.
//
// UI Pass 2 (most structurally significant change in the pass): a two-column
// layout at `md`+ with a sticky right sidebar (asking price + the access/gate
// panel); on narrower viewports the page reflows to price → gate → the rest of
// the content, because the gate is the point of the page and should not be
// buried at the bottom on mobile. No gate logic changed — `RequestAccessPanel`
// is only repositioned, never edited (Pass 3 owns its internals).
import { useEffect, useState } from 'react'
import { observer } from 'mobx-react-lite'
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  Container,
  Skeleton,
  Stack,
  Typography,
} from '@mui/material'
import { Link as RouterLink, useParams } from 'react-router-dom'
import { ApiError, publicApi } from '../lib/api'
import { GatedPanel } from './GatedPanel'
import { listingTypeLabel } from '../lib/listingTypes'
import { IdentityTile, type PublicListing } from './ListingCard'
import { Metric } from './Metric'
import { OfferForm } from './OfferForm'
import { RequestAccessPanel } from './RequestAccessPanel'
import { WatchlistButton } from './WatchlistButton'
import { accessStore } from '../stores/accessStore'
import { authStore } from '../stores/authStore'
import { metricLabel, metricValue, surfaceRecessed } from '../theme'

function money(value: string): string {
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}

// "Listed N days ago" — the audit found `published_at` is fetched but never
// rendered anywhere on this page.
function timeAgo(iso: string | null): string | null {
  if (!iso) return null
  const then = new Date(iso).getTime()
  if (!Number.isFinite(then)) return null
  const days = Math.floor((Date.now() - then) / (1000 * 60 * 60 * 24))
  if (days <= 0) return 'Listed today'
  if (days === 1) return 'Listed 1 day ago'
  return `Listed ${days} days ago`
}

// A page-shaped skeleton, roughly matching the two-column layout below, so
// loading doesn't collapse to an unrelated centred spinner.
function DetailSkeleton() {
  return (
    <Box
      role="status"
      aria-label="Loading listing"
      sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: { xs: 3, md: 4 } }}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Stack spacing={3}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Skeleton variant="circular" width={48} height={48} />
            <Skeleton variant="rounded" width={80} height={24} />
          </Stack>
          <Skeleton variant="rounded" height={40} width="70%" />
          <Skeleton variant="rounded" height={140} />
          <Skeleton variant="rounded" height={100} />
        </Stack>
      </Box>
      <Box sx={{ width: { xs: '100%', md: 340 }, flexShrink: 0 }}>
        <Stack spacing={2}>
          <Skeleton variant="rounded" height={90} />
          <Skeleton variant="rounded" height={160} />
        </Stack>
      </Box>
    </Box>
  )
}

// The gate, made visible for an anonymous visitor — UI Pass 3 consolidated
// this onto the shared `GatedPanel` (see that file). Every existing sentence
// is unchanged.
function AnonymousGateCard() {
  return (
    <GatedPanel variant="locked" size="full" redactedFields={['Company name', 'Website', 'Detailed financials']}>
      <Typography variant="h6" component="h2">
        Locked until the NDA is signed
      </Typography>
      <Typography variant="body2" color="text.secondary">
        The company name, website, and detailed financials become available once you
        sign the platform NDA and the seller approves your request.
      </Typography>
      <Button component={RouterLink} to="/login" variant="contained" sx={{ mt: 1, alignSelf: 'flex-start' }}>
        Sign in to request access
      </Button>
    </GatedPanel>
  )
}

export const ListingDetail = observer(function ListingDetail() {
  const { id } = useParams()
  const [listing, setListing] = useState<PublicListing | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setListing(null)
    setError(null)
    publicApi(`/listings/${id}`)
      .then((data: PublicListing) => {
        if (!cancelled) setListing(data)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        // A 404 here means "not publicly available" and nothing more — never
        // "this listing exists but is in draft".
        setError(
          e instanceof ApiError && e.status === 404
            ? 'This listing is not available.'
            : e instanceof Error
              ? e.message
              : String(e),
        )
      })
    return () => {
      cancelled = true
    }
  }, [id])

  const listedAgo = listing ? timeAgo(listing.published_at) : null

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, sm: 5 } }}>
      <Button component={RouterLink} to="/browse" sx={{ mb: 2, ml: -1 }}>
        <Box aria-hidden component="span" sx={{ mr: 0.75 }}>
          ←
        </Box>
        Back to browse
      </Button>

      {error && <Alert severity="error">{error}</Alert>}

      {!error && listing === null && <DetailSkeleton />}

      {!error && listing && (
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', md: 'row' },
            gap: { xs: 3, md: 4 },
            alignItems: 'flex-start',
          }}
        >
          {/* Main content. Mobile order 2 — the sidebar (price + gate) comes
              first on narrow viewports (see below). */}
          <Box sx={{ order: { xs: 2, md: 1 }, flex: 1, minWidth: 0, width: '100%' }}>
            <Stack spacing={3}>
              <Stack spacing={1.5}>
                <Stack direction="row" spacing={1.5} alignItems="center">
                  <IdentityTile id={listing.id} type={listing.type} />
                  <Chip label={listingTypeLabel(listing.type)} size="small" />
                  <Box sx={{ flexGrow: 1 }} />
                  {/* M9 — not nested inside any clickable region on this page,
                      so no CardActionArea-style nesting hazard here. */}
                  <WatchlistButton listingId={Number(id)} />
                </Stack>
                <Typography variant="h3" component="h1" sx={{ overflowWrap: 'anywhere' }}>
                  {listing.headline}
                </Typography>
                {listedAgo && (
                  <Typography variant="body2" color="text.secondary">
                    {listedAgo}
                  </Typography>
                )}
              </Stack>

              <Card sx={{ p: 3 }}>
                <Stack spacing={3}>
                  <Box>
                    <Typography variant="overline" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
                      TTM performance
                    </Typography>
                    <Box
                      sx={{
                        ...surfaceRecessed,
                        p: 2,
                        display: 'grid',
                        gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(3, 1fr)' },
                        gap: 3,
                      }}
                    >
                      <Metric label="TTM revenue" value={money(listing.ttm_revenue)} />
                      <Metric label="TTM profit" value={money(listing.ttm_profit)} />
                      <Metric label="MRR" value={money(listing.mrr)} />
                    </Box>
                  </Box>
                  <Box>
                    <Typography variant="overline" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
                      Customers
                    </Typography>
                    <Box
                      sx={{
                        ...surfaceRecessed,
                        p: 2,
                        display: 'grid',
                        gridTemplateColumns: 'repeat(2, 1fr)',
                        gap: 3,
                      }}
                    >
                      <Metric label="Customers" value={listing.customers.toLocaleString('en-US')} />
                      <Metric label="Monthly churn" value={`${listing.churn_pct}%`} />
                    </Box>
                  </Box>
                </Stack>
              </Card>

              <Stack spacing={1}>
                <Typography variant="overline" color="text.secondary">
                  About this business
                </Typography>
                <Typography
                  color="text.secondary"
                  sx={{ whiteSpace: 'pre-wrap', maxWidth: '68ch', lineHeight: 1.7 }}
                >
                  {listing.description}
                </Typography>
              </Stack>
            </Stack>
          </Box>

          {/* Sticky sidebar: asking price + the gate. Mobile order 1 — shown
              before the rest of the content (mobile-first priority: the gate
              is the point of the page). */}
          <Box
            sx={{
              order: { xs: 1, md: 2 },
              width: { xs: '100%', md: 340 },
              flexShrink: 0,
              position: { md: 'sticky' },
              top: { md: 96 },
            }}
          >
            <Stack spacing={2}>
              <Card sx={{ p: 3 }}>
                <Typography component="div" sx={metricLabel}>
                  Asking price
                </Typography>
                <Typography component="div" sx={{ ...metricValue, fontSize: '2rem' }}>
                  {money(listing.asking_price)}
                </Typography>
              </Card>

              {/* M5 — the gate, live. An authenticated visitor gets the real
                  panel (request / pending / approved / denied); an anonymous
                  one keeps the static teaser, because this route is
                  deliberately public (spec 004 F9) and the panel calls
                  authenticated endpoints. Signing in is the first step of
                  asking for access, so the teaser is the honest anonymous
                  view rather than a degraded one. */}
              {authStore.isAuthenticated ? (
                <>
                  <RequestAccessPanel listingId={Number(id)} />
                  {/* M7 — the offer panel (spec 007 J1, J2). Only once access
                      is actually unlocked: an offer requires approved access
                      server-side (`require_approved_buyer`, A2), so showing
                      the form any earlier would just be inviting a 403
                      `nda_access_required` this route guard already knows
                      about. */}
                  {accessStore.status === 'unlocked' && <OfferForm listingId={Number(id)} />}
                </>
              ) : (
                <AnonymousGateCard />
              )}
            </Stack>
          </Box>
        </Box>
      )}
    </Container>
  )
})
