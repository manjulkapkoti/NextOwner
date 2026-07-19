// M4 — the public marketplace (spec 004 criteria F2-F6, F9, E-4).
//
// Filters live in the URL query string, not just in component state, so a
// filtered view is linkable and survives a refresh — the thing a buyer wants to
// send a partner is "these listings", not "the marketplace, go find them again".
//
// State is local `useState` rather than a MobX store: this screen owns its data
// and nothing else reads it, which is the same call `MyListings` made. A store
// earns its place when a second consumer appears (the watchlist, at M9).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  Container,
  MenuItem,
  Pagination,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useSearchParams } from 'react-router-dom'
import { publicApi } from '../lib/api'
import { LISTING_TYPES } from '../lib/listingTypes'
import { ListingCard, type PublicListing } from './ListingCard'

const PAGE_SIZE = 20

// "No type filter" is a real, selectable option, so it needs a real value.
// MUI treats `value=""` as *empty* and renders a zero-width space instead of
// the matching menu item — which left the control looking blank with its label
// sitting where the value should be. A sentinel avoids that entirely; the URL
// still carries no `type` param when it is selected.
const ALL_TYPES = 'all'

const TYPES = [{ value: ALL_TYPES, label: 'All types' }, ...LISTING_TYPES]

interface Page {
  items: PublicListing[]
  total: number
  limit: number
  offset: number
}

export function BrowseListings() {
  const [params, setParams] = useSearchParams()
  const [page, setPage] = useState<Page | null>(null)
  const [error, setError] = useState<string | null>(null)

  // The search box is uncontrolled-by-URL while typing: writing every keystroke
  // to the query string would push a history entry per character.
  const [term, setTerm] = useState(params.get('q') ?? '')
  const type = params.get('type') ?? ''
  const minProfit = params.get('min_profit') ?? ''
  const maxPrice = params.get('max_price') ?? ''
  const pageNumber = Number(params.get('page') ?? '1')

  const query = useMemo(() => {
    const qs = new URLSearchParams()
    if (params.get('q')) qs.set('q', params.get('q')!)
    if (type) qs.set('type', type)
    if (minProfit) qs.set('min_profit', minProfit)
    if (maxPrice) qs.set('max_price', maxPrice)
    qs.set('limit', String(PAGE_SIZE))
    qs.set('offset', String((Math.max(pageNumber, 1) - 1) * PAGE_SIZE))
    return qs.toString()
  }, [params, type, minProfit, maxPrice, pageNumber])

  useEffect(() => {
    let cancelled = false
    setPage(null)
    setError(null)
    publicApi(`/listings?${query}`)
      .then((data: Page) => {
        if (!cancelled) setPage(data)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      })
    return () => {
      cancelled = true
    }
  }, [query])

  // Debounced, so a typed word is one request rather than one per character.
  const debounce = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const onSearch = useCallback(
    (value: string) => {
      setTerm(value)
      clearTimeout(debounce.current)
      debounce.current = setTimeout(() => {
        setParams((prev) => {
          const next = new URLSearchParams(prev)
          if (value) next.set('q', value)
          else next.delete('q')
          next.delete('page')
          return next
        })
      }, 250)
    },
    [setParams],
  )

  function setFilter(key: string, value: string) {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value) next.set(key, value)
      else next.delete(key)
      // Changing a *filter* returns you to page 1 — page 4 of the old result
      // set is meaningless against a new one. Changing the page itself must
      // obviously not reset the page.
      if (key !== 'page') next.delete('page')
      return next
    })
  }

  const hasFilters = Boolean(params.get('q') || type || minProfit || maxPrice)
  const pageCount = page ? Math.ceil(page.total / PAGE_SIZE) : 0

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, sm: 5 } }}>
      <Stack spacing={0.5} sx={{ mb: 3 }}>
        <Typography variant="h4" component="h1">
          Browse businesses
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {page ? `${page.total} ${page.total === 1 ? 'listing' : 'listings'}` : 'Loading listings'}
        </Typography>
      </Stack>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '260px minmax(0, 1fr)' },
          gap: { xs: 2, md: 4 },
          alignItems: 'start',
        }}
      >
        <Card component="aside" sx={{ p: 2.5, position: { md: 'sticky' }, top: 88 }}>
          <Stack spacing={2.5}>
            <TextField
              label="Search"
              placeholder="e.g. clinics"
              value={term}
              onChange={(e) => onSearch(e.target.value)}
              size="small"
              fullWidth
            />
            <TextField
              select
              label="Type"
              value={type || ALL_TYPES}
              onChange={(e) =>
                setFilter('type', e.target.value === ALL_TYPES ? '' : e.target.value)
              }
              size="small"
              fullWidth
            >
              {TYPES.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Max asking price"
              type="number"
              value={maxPrice}
              onChange={(e) => setFilter('max_price', e.target.value)}
              size="small"
              fullWidth
            />
            <TextField
              label="Min TTM profit"
              type="number"
              value={minProfit}
              onChange={(e) => setFilter('min_profit', e.target.value)}
              size="small"
              fullWidth
            />
            {hasFilters && (
              <Button
                onClick={() => {
                  setTerm('')
                  setParams(new URLSearchParams())
                }}
              >
                Clear all
              </Button>
            )}
          </Stack>
        </Card>

        <Box>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              Couldn't load listings: {error}
            </Alert>
          )}

          {!error && page === null && (
            <Stack alignItems="center" sx={{ py: 10 }}>
              <CircularProgress aria-label="loading listings" />
            </Stack>
          )}

          {!error && page?.items.length === 0 && (
            <Card sx={{ p: { xs: 4, sm: 6 }, textAlign: 'center' }}>
              <Typography variant="h6" sx={{ mb: 1 }}>
                No listings match these filters.
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Try widening the price range or clearing the search.
              </Typography>
            </Card>
          )}

          {!error && page && page.items.length > 0 && (
            <>
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, minmax(0, 1fr))' },
                  gap: 2.5,
                }}
              >
                {page.items.map((listing) => (
                  <ListingCard key={listing.id} listing={listing} />
                ))}
              </Box>

              {pageCount > 1 && (
                <Stack alignItems="center" sx={{ mt: 4 }}>
                  <Pagination
                    count={pageCount}
                    page={Math.max(pageNumber, 1)}
                    onChange={(_, value) => setFilter('page', String(value))}
                  />
                </Stack>
              )}
            </>
          )}
        </Box>
      </Box>
    </Container>
  )
}
