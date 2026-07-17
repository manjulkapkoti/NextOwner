// Login form — email + password, with loading / error / inline-422 states
// (spec H3, error_handling.md §3). A 422 maps each field-level error onto its
// field; anything else becomes a form-level message.
import { useState, type FormEvent } from 'react'
import { Alert, Box, Button, TextField } from '@mui/material'
import { authStore } from '../stores/authStore'

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
    <Box
      component="form"
      onSubmit={onSubmit}
      noValidate  // server owns validation (returns 422); no competing native popups
      sx={{ display: 'flex', flexDirection: 'column', gap: 2, maxWidth: 360 }}
    >
      {formError && <Alert severity="error">{formError}</Alert>}
      <TextField
        label="Email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={Boolean(fieldErrors.email)}
        helperText={fieldErrors.email}
      />
      <TextField
        label="Password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={Boolean(fieldErrors.password)}
        helperText={fieldErrors.password}
      />
      <Button type="submit" variant="contained" disabled={loading}>
        {loading ? 'Logging in…' : 'Log in'}
      </Button>
    </Box>
  )
}
