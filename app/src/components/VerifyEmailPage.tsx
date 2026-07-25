// M8 — confirm an email address (spec 008 J10).
//
// A rejected token is a dead end unless the page offers a way out, so the
// failure state carries a resend affordance rather than just an apology. The
// resend route is authenticated, which is why it is offered as a button here
// rather than fired automatically: an expired link may well be opened by
// someone who is not signed in.
import { useEffect, useState } from 'react'
import { Alert, Box, Button, CircularProgress, Stack, Typography } from '@mui/material'
import { useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'

type State = 'checking' | 'verified' | 'failed'

export function VerifyEmailPage() {
  const [params] = useSearchParams()
  const [state, setState] = useState<State>('checking')
  const [resent, setResent] = useState(false)

  useEffect(() => {
    api('/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token: params.get('token') ?? '' }),
    })
      .then(() => setState('verified'))
      .catch(() => setState('failed'))
  }, [params])

  async function resend() {
    try {
      await api('/auth/resend-verification', { method: 'POST' })
      setResent(true)
    } catch {
      setResent(false)
    }
  }

  if (state === 'checking') {
    return (
      <Box sx={{ py: 3, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress aria-label="Confirming your email address" size={28} />
      </Box>
    )
  }

  if (state === 'verified') {
    return (
      <Alert severity="success" role="status">
        Your email address is confirmed. You will now receive NextOwner email.
      </Alert>
    )
  }

  return (
    <Stack spacing={2} sx={{ maxWidth: 420 }}>
      <Typography variant="h5">We could not confirm that link</Typography>
      <Alert severity="error" role="alert">
        That confirmation link is invalid or has expired.
      </Alert>
      <Button variant="contained" onClick={() => void resend()}>
        Resend confirmation email
      </Button>
      {resent && (
        <Alert severity="success" role="status">
          A new confirmation email is on its way.
        </Alert>
      )}
    </Stack>
  )
}
