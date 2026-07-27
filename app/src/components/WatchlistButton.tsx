// M9 — the watchlist toggle (spec 009 plan § Frontend), a small heart
// affordance on listing surfaces (ListingCard, ListingDetail).
//
// UI Pass 4: real `Favorite`/`FavoriteBorder` icons from `@mui/icons-material`
// (now a dependency, added in Pass 1) replace the earlier hand-rolled
// Unicode heart pair (`♥`/`♡`), which rendered inconsistently across
// platforms/fonts.
import { useEffect, type MouseEvent } from 'react'
import { alpha, IconButton } from '@mui/material'
import FavoriteIcon from '@mui/icons-material/Favorite'
import FavoriteBorderIcon from '@mui/icons-material/FavoriteBorder'
import { observer } from 'mobx-react-lite'
import { authStore } from '../stores/authStore'
import { watchlistStore } from '../stores/watchlistStore'
import { motion } from '../theme'

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
        bgcolor: alpha('#fff', 0.9),
        backdropFilter: 'blur(4px)',
        boxShadow: 1,
        transition: `transform ${motion.fast}ms ${motion.easing}, background-color ${motion.fast}ms ${motion.easing}`,
        '&:hover': { bgcolor: alpha('#fff', 0.9), transform: 'scale(1.08)' },
        '@media (prefers-reduced-motion: reduce)': {
          '&:hover': { transform: 'none' },
        },
      }}
    >
      {watchlisted ? (
        <FavoriteIcon aria-hidden fontSize="small" sx={{ color: 'error.main' }} />
      ) : (
        <FavoriteBorderIcon aria-hidden fontSize="small" sx={{ color: 'text.secondary' }} />
      )}
    </IconButton>
  )
})
