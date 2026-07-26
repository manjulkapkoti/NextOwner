// M9 — the watchlist page (spec 009 plan § Frontend), reachable at /watchlist.
//
// Reuses ListingCard for each row — the same anonymous-card rendering the
// browse grid uses — mapped from `WatchlistEntryRead`'s `listing_id` to
// ListingCard's `id` (the two shapes are NOT drop-in compatible; see the note
// in watchlistStore.ts). ListingCard already carries a WatchlistButton (M9),
// so un-favoriting from here needs no separate control: the same heart toggle
// that adds a listing elsewhere removes it here.
import { useEffect } from 'react'
import { Alert, Box, CircularProgress, Stack, Typography } from '@mui/material'
import { observer } from 'mobx-react-lite'
import { ListingCard, type PublicListing } from './ListingCard'
import { watchlistStore } from '../stores/watchlistStore'

export const Watchlist = observer(function Watchlist() {
  useEffect(() => {
    if (!watchlistStore.loaded) {
      void watchlistStore.load()
    }
  }, [])

  if (watchlistStore.error) {
    return (
      <Alert severity="error" role="alert">
        {watchlistStore.error}
      </Alert>
    )
  }

  if (watchlistStore.loading && !watchlistStore.loaded) {
    return (
      <Stack alignItems="center" sx={{ py: 6 }}>
        <CircularProgress aria-label="loading watchlist" />
      </Stack>
    )
  }

  if (watchlistStore.entries.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        Your watchlist is empty. Favorite a listing from Browse to see it here.
      </Typography>
    )
  }

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' },
        gap: 2,
      }}
    >
      {watchlistStore.entries.map((entry) => {
        const listing: PublicListing = {
          id: entry.listing_id,
          type: entry.type,
          headline: entry.headline,
          description: entry.description,
          asking_price: entry.asking_price,
          ttm_revenue: entry.ttm_revenue,
          ttm_profit: entry.ttm_profit,
          mrr: entry.mrr,
          churn_pct: entry.churn_pct,
          customers: entry.customers,
          published_at: entry.published_at,
        }
        return <ListingCard key={entry.listing_id} listing={listing} />
      })}
    </Box>
  )
})
