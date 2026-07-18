// Registration form (FR-1/FR-2) — email, password, role. Mirrors LoginForm's
// loading / error / inline-422 states. Register returns no token (unlike
// login), so success sends the visitor to /login to sign in.
import { useState, type FormEvent } from 'react'
import { Alert, Box, Button, Link as MuiLink, MenuItem, TextField } from '@mui/material'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { ApiError, api } from '../lib/api'

type Role = 'buyer' | 'seller'

export function RegisterForm() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('buyer')
  const [loading, setLoading] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setFormError(null)
    setFieldErrors({})
    try {
      await api('/auth/register', { method: 'POST', body: JSON.stringify({ email, password, role }) })
      navigate('/login')
    } catch (err) {
      if (err instanceof ApiError && err.status === 422 && Array.isArray(err.detail)) {
        const errs: Record<string, string> = {}
        for (const item of err.detail as Array<{ loc: (string | number)[]; msg: string }>) {
          const field = item.loc[item.loc.length - 1]
          if (field) errs[String(field)] = item.msg
        }
        setFieldErrors(errs)
      } else if (err instanceof ApiError) {
        setFormError(err.message)
      } else {
        setFormError('Connection lost — please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box
      component="form"
      onSubmit={onSubmit}
      noValidate
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
      <TextField select label="I am a…" value={role} onChange={(e) => setRole(e.target.value as Role)}>
        <MenuItem value="buyer">Buyer</MenuItem>
        <MenuItem value="seller">Seller</MenuItem>
      </TextField>
      <Button type="submit" variant="contained" disabled={loading}>
        {loading ? 'Creating account…' : 'Create account'}
      </Button>
      <MuiLink component={RouterLink} to="/login" variant="body2">
        Already have an account? Log in
      </MuiLink>
    </Box>
  )
}
