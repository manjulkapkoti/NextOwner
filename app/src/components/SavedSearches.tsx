// M8 — saved searches (spec 008 J7, FR-11).
//
// The filter fields mirror the public browse filters exactly, because the
// server validates both with the same schema: a field that cannot be browsed
// on cannot be saved on either (spec S5).
import { useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { api, ApiError } from '../lib/api'
import { LISTING_TYPES } from '../lib/listingTypes'
import { EmptyState } from './EmptyState'

interface SavedSearch {
  id: number
  name: string
  filters: Record<string, string | null>
  created_at: string
}

export function SavedSearches() {
  const [rows, setRows] = useState<SavedSearch[]>([])
  const [name, setName] = useState('')
  const [type, setType] = useState('')
  const [maxPrice, setMaxPrice] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    setRows((await api('/saved-searches')) as SavedSearch[])
  }

  useEffect(() => {
    void refresh().catch(() => setError('We could not load your saved searches.'))
  }, [])

  async function save() {
    setError(null)
    const filters: Record<string, string> = {}
    if (type) filters.type = type
    if (maxPrice) filters.max_price = maxPrice
    try {
      await api('/saved-searches', {
        method: 'POST',
        body: JSON.stringify({ name, filters }),
      })
      setName('')
      await refresh()
    } catch (err) {
      // 409 is the per-user cap, not a bug — say so plainly rather than
      // showing a generic failure the user cannot act on.
      setError(
        err instanceof ApiError && err.code === 'saved_search_limit'
          ? 'You have reached the maximum number of saved searches.'
          : 'We could not save that search.',
      )
    }
  }

  async function remove(id: number) {
    await api(`/saved-searches/${id}`, { method: 'DELETE' })
    await refresh()
  }

  return (
    <Stack spacing={3}>
      <Box component="section">
        <Typography variant="h6" gutterBottom>
          Save this search
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="flex-start">
          <TextField
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            fullWidth
          />
          <TextField
            select
            label="Type"
            value={type}
            onChange={(e) => setType(e.target.value)}
            sx={{ minWidth: 160 }}
          >
            <MenuItem value="">Any</MenuItem>
            {LISTING_TYPES.map((t) => (
              <MenuItem key={t.value} value={t.value}>
                {t.label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Max price"
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            sx={{ minWidth: 160 }}
          />
          <Button variant="contained" onClick={() => void save()} disabled={!name.trim()}>
            Save search
          </Button>
        </Stack>
      </Box>

      {error && (
        <Alert severity="error" role="alert">
          {error}
        </Alert>
      )}

      {rows.length === 0 ? (
        <EmptyState message="No saved searches yet." />
      ) : (
        <Stack spacing={1.5}>
          {rows.map((row) => (
            <Card key={row.id} variant="outlined">
              <CardContent
                sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
              >
                <Typography>{row.name}</Typography>
                <Button
                  size="small"
                  color="error"
                  aria-label={`Delete ${row.name}`}
                  onClick={() => void remove(row.id)}
                >
                  Delete
                </Button>
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}
    </Stack>
  )
}
