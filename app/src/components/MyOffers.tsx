// M7 — the buyer's own cross-listing offers dashboard (spec 007, plan.md §
// Frontend; user story 8 — "As either party, I want to see the full history
// of offers and counters"). The buyer-side mirror of the backend's own
// `GET /my/offers` (F1-F3): every thread, across every listing, grouped by
// the listing it belongs to.
import { useEffect, useState } from 'react'
import { observer } from 'mobx-react-lite'
import { Alert, Box, CircularProgress, Stack, Typography } from '@mui/material'
import { offerStore } from '../stores/offerStore'
import { OfferThread } from './OfferThread'

export const MyOffers = observer(function MyOffers() {
  const [status, setStatus] = useState<'loading' | 'ready' | 'errored'>('loading')

  useEffect(() => {
    let cancelled = false
    offerStore
      .loadMyOffers()
      .then(() => {
        if (!cancelled) setStatus('ready')
      })
      .catch(() => {
        if (!cancelled) setStatus('errored')
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (status === 'loading') {
    return (
      <Box sx={{ py: 3, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress aria-label="Loading your offers" size={28} />
      </Box>
    )
  }

  if (status === 'errored') {
    return (
      <Alert severity="error" role="alert">
        We could not load your offers.
      </Alert>
    )
  }

  // Every listing the buyer has a thread on, in first-seen order.
  const listingIds = Array.from(new Set(offerStore.myOffers.map((row) => row.listing_id)))

  if (listingIds.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
        You haven&apos;t made any offers yet.
      </Typography>
    )
  }

  return (
    <Stack spacing={4}>
      {listingIds.map((listingId) => (
        <Box key={listingId}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
            Listing #{listingId}
          </Typography>
          <OfferThread
            rows={offerStore.offersForListing(listingId)}
            viewerRole="buyer"
            onChange={() => void offerStore.loadMyOffers()}
          />
        </Box>
      ))}
    </Stack>
  )
})
