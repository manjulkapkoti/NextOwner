// Login form — email + password, with loading / error / inline-422 states
// (spec H3, error_handling.md §3). A 422 maps each field-level error onto its
// field; anything else becomes a form-level message.
//
// Presentation is a centered auth card (design_system.md); all behaviour —
// the 422 mapping, loading state, noValidate, the register link — is unchanged.
import { useState, type FormEvent } from 'react'
import { Alert, Box, Button, Card, Link as MuiLink, Stack, TextField, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import { authStore } from '../stores/authStore'
import { Wordmark } from './Wordmark'

export function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setFormError(null)
    setFieldErrors({})
    try {
      // Post directly (OAuth2 password form is form-encoded, not JSON), so we can
      // read the 422 field-level shape before it becomes an ApiError.
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: email, password }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        if (res.status === 422 && Array.isArray(body?.detail)) {
          const errs: Record<string, string> = {}
          for (const item of body.detail) {
            const field = item.loc?.[item.loc.length - 1]
            if (field) errs[String(field)] = item.msg
          }
          setFieldErrors(errs)
        } else {
          setFormError(typeof body?.detail === 'string' ? body.detail : 'Login failed')
        }
        return
      }
      const data = await res.json()
      authStore.setToken(data.access_token)
      await authStore.loadUser()
    } catch {
      setFormError('Connection lost — please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card sx={{ width: '100%', maxWidth: 440, mx: 'auto', p: { xs: 3, sm: 4 } }}>
      <Stack spacing={0.75} alignItems="center" sx={{ mb: 3, textAlign: 'center' }}>
        <Box sx={{ mb: 1 }}>
          <Wordmark height={32} />
        </Box>
        <Typography variant="h5" component="h1">
          Welcome back
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Log in to continue to your account
        </Typography>
      </Stack>

      <Box
        component="form"
        onSubmit={onSubmit}
        noValidate // server owns validation (returns 422); no competing native popups
        sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}
      >
        {formError && <Alert severity="error">{formError}</Alert>}
        <TextField
          label="Email"
          type="email"
          fullWidth
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={Boolean(fieldErrors.email)}
          helperText={fieldErrors.email}
        />
        <TextField
          label="Password"
          type="password"
          fullWidth
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={Boolean(fieldErrors.password)}
          helperText={fieldErrors.password}
        />
        <Button type="submit" variant="contained" size="large" fullWidth disabled={loading}>
          {loading ? 'Logging in…' : 'Log in'}
        </Button>
      </Box>

      <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 3 }}>
        New here?{' '}
        <MuiLink component={RouterLink} to="/register" sx={{ fontWeight: 600 }}>
          Create an account
        </MuiLink>
      </Typography>
    </Card>
  )
}
