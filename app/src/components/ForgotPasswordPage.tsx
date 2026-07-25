// M8 — request a password reset (spec 008 J8).
//
// **The UI must not leak what the API deliberately refuses to.** The server
// answers 202 for every address, known or not (spec G2); this page therefore
// shows one fixed confirmation and never branches on the response. A "no
// account with that email" message here would hand back the exact enumeration
// oracle the endpoint was designed to close.
import { useState } from 'react'
import { Alert, Box, Button, Stack, TextField, Typography } from '@mui/material'
import { api } from '../lib/api'

const CONFIRMATION =
  'If an account exists for that address, we have sent a link to reset the password.'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      await api('/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email }),
      })
    } catch {
      // Deliberately swallowed. A rate-limit or transport failure must not
      // become a signal about whether the address exists.
    } finally {
      setBusy(false)
      setSent(true)
    }
  }

  return (
    <Box component="form" onSubmit={submit} sx={{ maxWidth: 420 }}>
      <Typography variant="h5" gutterBottom>
        Reset your password
      </Typography>
      <Stack spacing={2}>
        <TextField
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          fullWidth
        />
        <Button type="submit" variant="contained" disabled={busy}>
          Send reset link
        </Button>
        {sent && (
          <Alert severity="success" role="status">
            {CONFIRMATION}
          </Alert>
        )}
      </Stack>
    </Box>
  )
}
