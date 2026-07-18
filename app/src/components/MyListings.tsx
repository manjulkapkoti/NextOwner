// M2 — the seller dashboard (spec H2; FR-8). Lists the caller's own listings
// with status; shows empty / loading / error states.
import { useEffect, useState } from 'react'
import { Alert, Box, Chip, CircularProgress, List, ListItem, ListItemText, Typography } from '@mui/material'
import { api } from '../lib/api'

interface ListingRow {
  id: number
  headline: string
  status: string
}

export function MyListings() {
  const [rows, setRows] = useState<ListingRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api('/my/listings')
      .then((data) => setRows(data))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  if (error) return <Alert severity="error">Couldn't load your listings: {error}</Alert>
  if (rows === null) return <CircularProgress aria-label="loading your listings" />
  if (rows.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary">No listings yet — create your first one.</Typography>
      </Box>
    )
  }

  return (
    <List>
      {rows.map((row) => (
        <ListItem key={row.id} secondaryAction={<Chip label={row.status} size="small" />}>
          <ListItemText primary={row.headline} />
        </ListItem>
      ))}
    </List>
  )
}
