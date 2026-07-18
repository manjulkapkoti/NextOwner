// Registration form (FR-1/FR-2) — email, password, role. Mirrors LoginForm's
// loading / error / inline-422 states. Register returns no token (unlike
// login), so success sends the visitor to /login to sign in.
//
// Presentation matches LoginForm's centered auth card (design_system.md); all
// behaviour — the 422 mapping, role select, navigation on success — is unchanged.
import { useState, type FormEvent } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  Link as MuiLink,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
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
    <Card sx={{ width: '100%', maxWidth: 440, mx: 'auto', p: { xs: 3, sm: 4 } }}>
      <Stack spacing={0.75} sx={{ mb: 3, textAlign: 'center' }}>
        <Typography variant="overline" sx={{ color: 'primary.main' }}>
          NextOwner
        </Typography>
        <Typography variant="h5" component="h1">
          Create your account
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Join the marketplace to buy or sell online businesses
        </Typography>
      </Stack>

      <Box
        component="form"
        onSubmit={onSubmit}
        noValidate
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
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={Boolean(fieldErrors.password)}
          helperText={fieldErrors.password}
        />
        <TextField
          select
          fullWidth
          label="I am a…"
          value={role}
          onChange={(e) => setRole(e.target.value as Role)}
        >
          <MenuItem value="buyer">Buyer</MenuItem>
          <MenuItem value="seller">Seller</MenuItem>
        </TextField>
        <Button type="submit" variant="contained" size="large" fullWidth disabled={loading}>
          {loading ? 'Creating account…' : 'Create account'}
        </Button>
      </Box>

      <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 3 }}>
        Already have an account?{' '}
        <MuiLink component={RouterLink} to="/login" sx={{ fontWeight: 600 }}>
          Log in
        </MuiLink>
      </Typography>
    </Card>
  )
}
