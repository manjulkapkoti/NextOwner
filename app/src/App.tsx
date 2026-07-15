import { useEffect, useState } from 'react'
import { Alert, Box, CircularProgress, Container, Typography } from '@mui/material'
import { api } from './lib/api'

// Milestone 0 page — calls GET /api/health and shows the result, proving the
// React → Vite proxy → FastAPI round trip end to end.
export default function App() {
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api('/health')
      .then((data) => setStatus(data.status))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  return (
    <Container maxWidth="sm">
      <Box sx={{ mt: 8, textAlign: 'center' }}>
        <Typography variant="h3" gutterBottom>
          NextOwner
        </Typography>
        <Typography variant="body1" color="text.secondary" gutterBottom>
          Marketplace scaffold — Milestone 0
        </Typography>
        <Box sx={{ mt: 3 }}>
          {status && <Alert severity="success">API health: {status}</Alert>}
          {error && <Alert severity="error">API unreachable: {error}</Alert>}
          {!status && !error && <CircularProgress aria-label="checking API health" />}
        </Box>
      </Box>
    </Container>
  )
}
