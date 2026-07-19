// M4 — the public listing detail at /browse/:id (spec 004 C1-C4).
//
// Same anonymity rules as the card: this renders only fields the public schema
// carries. A non-live or missing listing is a 404 from the server and shows the
// same "not available" message here — the client must not become the existence
// oracle the API deliberately isn't.
import { useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Container,
  Divider,
  Stack,
  Typography,
} from '@mui/material'
import { Link as RouterLink, useParams } from 'react-router-dom'
import { ApiError, publicApi } from '../lib/api'
import { listingTypeLabel } from '../lib/listingTypes'
import type { PublicListing } from './ListingCard'

function money(value: string): string {
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {label}
      </Typography>
      <Typography variant="h6" component="p">
        {value}
      </Typography>
    </Box>
  )
}

export function ListingDetail() {
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

  return (
    <Container maxWidth="md" sx={{ py: { xs: 3, sm: 5 } }}>
      <Button component={RouterLink} to="/browse" sx={{ mb: 2, ml: -1 }}>
        <Box aria-hidden component="span" sx={{ mr: 0.75 }}>
          ←
        </Box>
        Back to browse
      </Button>

      {error && <Alert severity="error">{error}</Alert>}

      {!error && listing === null && (
        <Stack alignItems="center" sx={{ py: 10 }}>
          <CircularProgress aria-label="loading listing" />
        </Stack>
      )}

      {!error && listing && (
        <Stack spacing={3}>
          <Stack spacing={1.5}>
            <Chip
              label={listingTypeLabel(listing.type)}
              size="small"
              sx={{ alignSelf: 'flex-start' }}
            />
            <Typography variant="h4" component="h1" sx={{ overflowWrap: 'anywhere' }}>
              {listing.headline}
            </Typography>
          </Stack>

          <Card sx={{ p: 3 }}>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(4, 1fr)' },
                gap: 3,
              }}
            >
              <Figure label="Asking price" value={money(listing.asking_price)} />
              <Figure label="TTM revenue" value={money(listing.ttm_revenue)} />
              <Figure label="TTM profit" value={money(listing.ttm_profit)} />
              <Figure label="MRR" value={money(listing.mrr)} />
            </Box>
            <Divider sx={{ my: 3 }} />
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(4, 1fr)' },
                gap: 3,
              }}
            >
              <Figure label="Customers" value={listing.customers.toLocaleString('en-US')} />
              <Figure label="Monthly churn" value={`${listing.churn_pct}%`} />
            </Box>
          </Card>

          <Stack spacing={1}>
            <Typography variant="h6" component="h2">
              About this business
            </Typography>
            <Typography color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
              {listing.description}
            </Typography>
          </Stack>

          <Card
            sx={{
              p: 3,
              bgcolor: 'action.hover',
              border: '1px dashed',
              borderColor: 'divider',
              boxShadow: 'none',
            }}
          >
            <Typography variant="h6" component="h2" sx={{ mb: 1 }}>
              Locked until the NDA is signed
            </Typography>
            <Typography variant="body2" color="text.secondary">
              The company name, website, and detailed financials become available once you sign the
              platform NDA and the seller approves your request.
            </Typography>
          </Card>
        </Stack>
      )}
    </Container>
  )
}
