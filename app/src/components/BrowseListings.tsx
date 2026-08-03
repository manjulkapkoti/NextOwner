// M4 — the public marketplace (spec 004 criteria F2-F6, F9, E-4).
//
// Filters live in the URL query string, not just in component state, so a
// filtered view is linkable and survives a refresh — the thing a buyer wants to
// send a partner is "these listings", not "the marketplace, go find them again".
//
// State is local `useState` rather than a MobX store: this screen owns its data
// and nothing else reads it, which is the same call `MyListings` made. A store
// earns its place when a second consumer appears (the watchlist, at M9).
//
// UI Pass 2: `PageHeader`, active-filter chips, a 3-up `lg` grid, skeleton
// loading, the shared `EmptyState`, and a rounded/primary pagination control.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  Divider,
  InputAdornment,
  MenuItem,
  Pagination,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useSearchParams } from 'react-router-dom'
import { publicApi } from '../lib/api'
import { LISTING_TYPES } from '../lib/listingTypes'
import { EmptyState } from './EmptyState'
import { ListingCard, ListingCardSkeleton, type PublicListing } from './ListingCard'
import { PageContainer, PageHeader } from './PageShell'

const PAGE_SIZE = 20
const SKELETON_COUNT = 6

// "No type filter" is a real, selectable option, so it needs a real value.
// MUI treats `value=""` as *empty* and renders a zero-width space instead of
// the matching menu item — which left the control looking blank with its label
// sitting where the value should be. A sentinel avoids that entirely; the URL
// still carries no `type` param when it is selected.
const ALL_TYPES = 'all'

const TYPES = [{ value: ALL_TYPES, label: 'All types' }, ...LISTING_TYPES]

// The grid template shared by the loaded grid and its skeleton twin — so the
// loading state never visibly reflows once real data arrives. `lg` adds a
// third column: below it, 2 columns keep cards from stretching over-wide.
const GRID_COLUMNS = {
  xs: '1fr',
  sm: 'repeat(2, minmax(0, 1fr))',
  lg: 'repeat(3, minmax(0, 1fr))',
}

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

  // Cancel a pending debounce on unmount (M13, spec 013 F7).
  //
  // Without this the timer outlives the component and fires `setParams` after
  // the visitor has navigated away — and `setParams` navigates the router, so
  // someone who clicks a result within 250ms of typing is thrown straight back
  // to the marketplace they just left. The fetch effect above already guards
  // exactly this hazard with its `cancelled` flag; this is the other half of
  // the same idea, and it was missing.
  //
  // Found by the golden path (spec 013), which fills and clicks faster than a
  // human usually does — but the race is reachable by hand whenever results
  // from a previous query are still on screen.
  useEffect(() => () => clearTimeout(debounce.current), [])

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

  // One handler, two callers (the rail's "Clear all" and the empty state's
  // "Clear all filters") — so they cannot drift into clearing different things.
  function clearAllFilters() {
    setTerm('')
    setParams(new URLSearchParams())
  }

  const hasFilters = Boolean(params.get('q') || type || minProfit || maxPrice)
  const pageCount = page ? Math.ceil(page.total / PAGE_SIZE) : 0

  // Active-filter chips above the grid — a user isn't forced back to the rail
  // to remove a single filter.
  const activeFilters: { key: string; label: string; onRemove: () => void }[] = []
  if (params.get('q')) {
    activeFilters.push({
      key: 'q',
      label: `Search: "${params.get('q')}"`,
      onRemove: () => {
        setTerm('')
        setFilter('q', '')
      },
    })
  }
  if (type) {
    activeFilters.push({
      key: 'type',
      label: `Type: ${TYPES.find((t) => t.value === type)?.label ?? type}`,
      onRemove: () => setFilter('type', ''),
    })
  }
  if (maxPrice) {
    activeFilters.push({
      key: 'max_price',
      label: `Under $${Number(maxPrice).toLocaleString('en-US')}`,
      onRemove: () => setFilter('max_price', ''),
    })
  }
  if (minProfit) {
    activeFilters.push({
      key: 'min_profit',
      label: `Min profit $${Number(minProfit).toLocaleString('en-US')}`,
      onRemove: () => setFilter('min_profit', ''),
    })
  }

  return (
    <PageContainer maxWidth="lg">
      <PageHeader
        title="Browse businesses"
        subtitle="Every listing's shape — metrics, growth, asking price — is visible before you sign anything. The identity behind it stays locked until the seller says yes."
        action={
          page && (
            <Chip label={`${page.total} ${page.total === 1 ? 'listing' : 'listings'}`} size="small" />
          )
        }
      />

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '260px minmax(0, 1fr)' },
          gap: { xs: 2, md: 4 },
          alignItems: 'start',
        }}
      >
        <Card component="aside" sx={{ p: 3, position: { md: 'sticky' }, top: 88 }}>
          <Stack spacing={2.5}>
            <Typography variant="overline" color="text.secondary">
              Filter
            </Typography>
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

            <Stack spacing={1.5}>
              <Typography variant="overline" color="text.secondary">
                Financials
              </Typography>
              <TextField
                label="Max asking price"
                type="number"
                value={maxPrice}
                onChange={(e) => setFilter('max_price', e.target.value)}
                size="small"
                fullWidth
                slotProps={{ input: { startAdornment: <InputAdornment position="start">$</InputAdornment> } }}
              />
              <TextField
                label="Min TTM profit"
                type="number"
                value={minProfit}
                onChange={(e) => setFilter('min_profit', e.target.value)}
                size="small"
                fullWidth
                slotProps={{ input: { startAdornment: <InputAdornment position="start">$</InputAdornment> } }}
              />
            </Stack>

            {hasFilters && (
              <Button variant="outlined" fullWidth size="small" onClick={clearAllFilters}>
                Clear all
              </Button>
            )}
          </Stack>
        </Card>

        <Box>
          {activeFilters.length > 0 && (
            <Stack direction="row" flexWrap="wrap" spacing={1} sx={{ mb: 2.5, rowGap: 1 }}>
              {activeFilters.map((filter) => (
                <Chip key={filter.key} label={filter.label} size="small" onDelete={filter.onRemove} />
              ))}
            </Stack>
          )}

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              Couldn't load listings: {error}
            </Alert>
          )}

          {!error && page === null && (
            <Box
              role="status"
              aria-label="Loading listings"
              sx={{ display: 'grid', gridTemplateColumns: GRID_COLUMNS, gap: 2.5 }}
            >
              {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
                <ListingCardSkeleton key={i} />
              ))}
            </Box>
          )}

          {!error && page?.items.length === 0 && (
            <EmptyState
              message="No listings match these filters. Try widening the price range or clearing the search."
              action={{ label: 'Clear all filters', onClick: clearAllFilters }}
            />
          )}

          {!error && page && page.items.length > 0 && (
            <>
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: GRID_COLUMNS,
                  gap: 2.5,
                }}
              >
                {page.items.map((listing) => (
                  <ListingCard key={listing.id} listing={listing} />
                ))}
              </Box>

              {pageCount > 1 && (
                <>
                  <Divider sx={{ mt: 5, mb: 3 }} />
                  <Stack alignItems="center">
                    <Pagination
                      count={pageCount}
                      page={Math.max(pageNumber, 1)}
                      onChange={(_, value) => setFilter('page', String(value))}
                      shape="rounded"
                      color="primary"
                    />
                  </Stack>
                </>
              )}
            </>
          )}
        </Box>
      </Box>
    </PageContainer>
  )
}
