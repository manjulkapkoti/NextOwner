// M9 — the watchlist toggle (spec 009 plan § Frontend), a small heart
// affordance on listing surfaces (ListingCard, ListingDetail).
//
// Hand-rolled glyph, not @mui/icons-material — that package is not a
// dependency of this app (see NavBar.tsx's MenuGlyph for the same pattern).
// A Unicode heart pair styled with `sx` renders reliably without adding one.
import { useEffect, type MouseEvent } from 'react'
import { Box, IconButton } from '@mui/material'
import { observer } from 'mobx-react-lite'
import { authStore } from '../stores/authStore'
import { watchlistStore } from '../stores/watchlistStore'

export const WatchlistButton = observer(function WatchlistButton({
  listingId,
}: {
  listingId: number
}) {
  // This component is instantiated once per card on a grid of many listings
  // — `loaded` guards against a fetch per instance, so only the first mount
  // (of whichever card renders first) triggers the request.
  useEffect(() => {
    if (authStore.isAuthenticated && !watchlistStore.loaded && !watchlistStore.loading) {
      void watchlistStore.load()
    }
  }, [])

  // An anonymous browser has no watchlist — don't show a button that would 401.
  if (!authStore.isAuthenticated) return null

  const watchlisted = watchlistStore.isWatchlisted(listingId)

  async function handleClick(e: MouseEvent) {
    // Defensive: this button is placed as a sibling of the card's clickable
    // area (ListingCard), never nested inside it, but stopping propagation
    // here costs nothing and protects any future placement.
    e.preventDefault()
    e.stopPropagation()
    try {
      if (watchlisted) {
        await watchlistStore.remove(listingId)
      } else {
        await watchlistStore.add(listingId)
      }
    } catch {
      // A convenience action, not a form submission — no page-level error
      // banner for a single card's toggle failing. The UI simply doesn't
      // update, which is the honest reflection of "that didn't work."
    }
  }

  return (
    <IconButton
      aria-label={watchlisted ? 'Remove from watchlist' : 'Add to watchlist'}
      onClick={(e) => void handleClick(e)}
      size="small"
      sx={{
        bgcolor: 'background.paper',
        boxShadow: 1,
        '&:hover': { bgcolor: 'background.paper' },
      }}
    >
      <Box
        aria-hidden
        component="span"
        sx={{
          fontSize: 18,
          lineHeight: 1,
          color: watchlisted ? 'error.main' : 'text.secondary',
        }}
      >
        {watchlisted ? '♥' : '♡'}
      </Box>
    </IconButton>
  )
})
