// M8 — choose a new password (spec 008 J9).
//
// The token comes from the query string because that is where the emailed link
// puts it, and it is sent to the API in the **body** (spec D11) — the server
// refuses it as a query parameter precisely so it never lands in an access log.
import { useState } from 'react'
import { Alert, Box, Button, Stack, TextField, Typography } from '@mui/material'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../lib/api'

/** Pull a field-level message out of FastAPI's 422 shape (error_handling.md §3). */
function fieldError(err: unknown, field: string): string | null {
  if (!(err instanceof ApiError) || err.status !== 422) return null
  const detail = err.detail
  if (!Array.isArray(detail)) return null
  const entry = detail.find(
    (d: { loc?: unknown[] }) => Array.isArray(d.loc) && d.loc.includes(field),
  ) as { msg?: string } | undefined
  return entry?.msg ?? null
}

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [failed, setFailed] = useState<string | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setPasswordError(null)
    setFailed(null)
    try {
      await api('/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({ token: params.get('token') ?? '', password }),
      })
      navigate('/login')
    } catch (err) {
      const inline = fieldError(err, 'password')
      if (inline) {
        setPasswordError(inline)
        return
      }
      setFailed(
        err instanceof ApiError && err.code === 'invalid_token'
          ? 'That link is invalid or has expired. Request a new one.'
          : 'We could not reset your password.',
      )
    }
  }

  return (
    <Box component="form" onSubmit={submit} sx={{ maxWidth: 420 }}>
      <Typography variant="h5" gutterBottom>
        Choose a new password
      </Typography>
      <Stack spacing={2}>
        <TextField
          label="New password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={passwordError !== null}
          helperText={passwordError ?? ' '}
          required
          fullWidth
        />
        <Button type="submit" variant="contained">
          Reset password
        </Button>
        {failed && (
          <Alert severity="error" role="alert">
            {failed}
          </Alert>
        )}
      </Stack>
    </Box>
  )
}
