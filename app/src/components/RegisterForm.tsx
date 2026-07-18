// Registration form (FR-1/FR-2) — email, password, role. Mirrors LoginForm's
// loading / error / inline-422 states. Register returns no token (unlike
// login), so success sends the visitor to /login to sign in.
//
// Layout follows a dedicated full-page signup (design_system.md): its own
// header (back + wordmark) instead of the app nav, a security reassurance
// panel up front, then the shortest possible form. Only the three fields the
// API actually accepts are asked for — email, password, role. All behaviour
// (the 422 mapping, navigation on success) is unchanged.
import { useState, type FormEvent } from 'react'
import {
  Alert,
  Box,
  Button,
  FormControl,
  FormControlLabel,
  FormLabel,
  Link as MuiLink,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { ApiError, api } from '../lib/api'
import { brandTint } from '../theme'

type Role = 'buyer' | 'seller'

// Small inline shield — avoids pulling in an icon package for one glyph.
function ShieldGlyph() {
  return (
    <Box
      aria-hidden
      component="svg"
      viewBox="0 0 24 24"
      sx={{ width: 22, height: 22, flexShrink: 0, color: 'primary.main', mt: '2px' }}
    >
      <path
        d="M12 2.5 4.5 5.8v5.4c0 4.6 3.2 8.9 7.5 10.3 4.3-1.4 7.5-5.7 7.5-10.3V5.8L12 2.5Z"
        fill="currentColor"
        opacity="0.14"
      />
      <path
        d="M12 2.5 4.5 5.8v5.4c0 4.6 3.2 8.9 7.5 10.3 4.3-1.4 7.5-5.7 7.5-10.3V5.8L12 2.5Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M9.6 12.2l1.7 1.7 3.3-3.4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Box>
  )
}

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
    <Box sx={{ width: '100%', maxWidth: 560, mx: 'auto' }}>
      <Typography variant="h4" component="h1" sx={{ mb: 3 }}>
        Get started with NextOwner
      </Typography>

      {/* Reassurance before the form, not after it: on a marketplace where the
          sensitive material sits behind an NDA, saying so up front is the
          reason someone is willing to type anything at all. */}
      <Stack
        direction="row"
        spacing={1.5}
        sx={{
          mb: 4,
          p: 2,
          borderRadius: 2,
          bgcolor: brandTint,
          border: '1px solid',
          borderColor: 'divider',
        }}
      >
        <ShieldGlyph />
        <Box>
          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
            Your security is our top priority
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Financials and other sensitive details stay private. Buyers see them only after
            signing our platform NDA and being approved by the seller.
          </Typography>
        </Box>
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
          helperText={fieldErrors.password || 'At least 8 characters.'}
        />

        <FormControl sx={{ mt: 1 }}>
          <FormLabel sx={{ typography: 'h6', color: 'text.primary', mb: 0.5 }}>I am a…</FormLabel>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            You can take on the other role later — this just sets up your dashboard.
          </Typography>
          <RadioGroup value={role} onChange={(e) => setRole(e.target.value as Role)}>
            <FormControlLabel
              value="buyer"
              control={<Radio />}
              label="Buyer — I'm looking to acquire a business"
            />
            <FormControlLabel
              value="seller"
              control={<Radio />}
              label="Seller — I have a business to list"
            />
          </RadioGroup>
        </FormControl>

        {/* The server stamps tos_accepted_at + tos_version on this request, so
            this sentence describes a record that is actually kept. */}
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
          By creating an account you agree to our Terms of Service, Privacy Policy, and platform
          Non-Disclosure Agreement.
        </Typography>

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
    </Box>
  )
}
