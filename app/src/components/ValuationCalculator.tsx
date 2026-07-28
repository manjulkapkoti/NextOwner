// M11 — the public valuation calculator (spec 011, F12/FR-23), at /valuation.
//
// The one screen in the app whose entire audience has never signed in. Everything
// else here assumes a session; this assumes the opposite, which is why it uses
// `publicApi` (no JWT, no global-401 bounce) and holds its state in the component
// rather than a MobX store (spec D13 — state with no second reader).
//
// The conversion shape is deliberate and is the whole feature: **answer first,
// ask second**. The estimate is rendered in full — range, explanation,
// disclaimer — before the email field is ever shown, and it stays on screen after
// capture (U6). A calculator that withholds the number until you pay in contact
// details is the pattern this one is competing against.
import { useState, type FormEvent } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { ApiError, publicApi } from '../lib/api'
import { LISTING_TYPES } from '../lib/listingTypes'
import { surfaceRecessed } from '../theme'

type Estimate = {
  low: string
  high: string
  driver: 'profit' | 'revenue' | 'none'
  explanation: string
  disclaimer: string
}

type Form = {
  type: string
  ttm_revenue: string
  ttm_profit: string
  growth_pct: string
  churn_pct: string
}

const EMPTY_FORM: Form = {
  type: 'saas',
  ttm_revenue: '',
  ttm_profit: '',
  growth_pct: '',
  churn_pct: '',
}

/** Money for humans: `300000` → `$300,000`.
 *
 * Deliberately no decimals — the server already quantized to whole units (spec
 * §6.5), and cents on a rule-of-thumb range would imply a precision the model
 * does not have.
 */
function money(value: string): string {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return value
  return parsed.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  })
}

/** Map FastAPI's native 422 shape to `{field: message}` (error_handling.md §1).
 *
 * The `loc` tail is the field name — `["body", "ttm_profit"]`. A cross-field
 * validator reports `["body"]` with no field, so those land under `_form` and
 * render as a banner rather than vanishing.
 */
function fieldErrors(detail: unknown): Record<string, string> {
  if (!Array.isArray(detail)) return {}
  const errors: Record<string, string> = {}
  for (const entry of detail) {
    const loc = (entry as { loc?: unknown[] })?.loc
    const msg = (entry as { msg?: string })?.msg
    if (!msg) continue
    const last = Array.isArray(loc) ? loc[loc.length - 1] : undefined
    const field = typeof last === 'string' && last !== 'body' ? last : '_form'
    // The server prefixes model-validator messages with "Value error, ".
    errors[field] = msg.replace(/^value error,\s*/i, '')
  }
  return errors
}

/** One error object → the message a stranger should read.
 *
 * 429 gets plain language, never the machine slug (U5): `rate_limited` is for
 * our branching, and a visitor who sees it learns nothing except that something
 * technical went wrong.
 */
function friendlyMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 429) {
      return "That's a few too many in a row — give it a minute and try again."
    }
    if (err.status >= 500) {
      return 'Something went wrong on our end. Please try again in a moment.'
    }
  }
  return 'We could not work that out just now. Please try again.'
}

export function ValuationCalculator() {
  const [form, setForm] = useState<Form>(EMPTY_FORM)
  const [estimate, setEstimate] = useState<Estimate | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const [email, setEmail] = useState('')
  const [captured, setCaptured] = useState(false)
  const [capturing, setCapturing] = useState(false)
  const [captureError, setCaptureError] = useState<string | null>(null)

  function update(field: keyof Form, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
    // Clear this field's error as soon as it's edited — leaving a stale message
    // under an input the visitor just fixed reads as "still wrong".
    setErrors((current) => {
      if (!current[field]) return current
      const rest = { ...current }
      delete rest[field]
      return rest
    })
  }

  /** Only the fields the visitor actually filled in. Sending `""` for an
   *  omitted optional would be a validation error for leaving a box blank —
   *  the server defaults them to neutral factors instead (spec C5). */
  function payload(): Record<string, string> {
    const body: Record<string, string> = { type: form.type }
    for (const key of ['ttm_revenue', 'ttm_profit', 'growth_pct', 'churn_pct'] as const) {
      if (form[key].trim()) body[key] = form[key].trim()
    }
    return body
  }

  async function handleCalculate(event: FormEvent) {
    event.preventDefault()
    setLoading(true)
    setErrors({})
    setMessage(null)
    try {
      const result = (await publicApi('/valuation', {
        method: 'POST',
        body: JSON.stringify(payload()),
      })) as Estimate
      setEstimate(result)
      // A fresh estimate invalidates a previous capture — the address on file
      // was sent against different numbers.
      setCaptured(false)
      setCaptureError(null)
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setErrors(fieldErrors(err.detail))
      } else {
        setMessage(friendlyMessage(err))
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleCapture(event: FormEvent) {
    event.preventDefault()
    setCapturing(true)
    setCaptureError(null)
    try {
      await publicApi('/valuation/leads', {
        method: 'POST',
        body: JSON.stringify({ ...payload(), email: email.trim() }),
      })
      setCaptured(true)
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setCaptureError(fieldErrors(err.detail).email ?? 'That email address does not look right.')
      } else {
        setCaptureError(friendlyMessage(err))
      }
    } finally {
      setCapturing(false)
    }
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" component="h1" gutterBottom>
          What is your business worth?
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 560 }}>
          A rough range in under a minute, using the multiples small internet
          businesses actually trade at. No account needed.
        </Typography>
      </Box>

      <Card sx={{ p: { xs: 2.5, sm: 3 } }}>
        <Box component="form" onSubmit={handleCalculate} noValidate>
          <Stack spacing={2.5}>
            {/* A **native** select, unlike the app's authed screens. This form's
                audience arrives cold and disproportionately on a phone, where the
                platform's own picker is the familiar, accessible control — and it
                needs no JS to open. */}
            <TextField
              select
              required
              label="Business type"
              value={form.type}
              onChange={(e) => update('type', e.target.value)}
              error={Boolean(errors.type)}
              helperText={errors.type ?? ' '}
              fullWidth
              slotProps={{ select: { native: true } }}
            >
              {LISTING_TYPES.map((entry) => (
                <option key={entry.value} value={entry.value}>
                  {entry.label}
                </option>
              ))}
            </TextField>

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField
                required
                label="Last 12 months revenue"
                value={form.ttm_revenue}
                onChange={(e) => update('ttm_revenue', e.target.value)}
                error={Boolean(errors.ttm_revenue)}
                helperText={errors.ttm_revenue ?? 'Total sales over the past year.'}
                fullWidth
                inputMode="decimal"
              />
              <TextField
                required
                label="Last 12 months profit"
                value={form.ttm_profit}
                onChange={(e) => update('ttm_profit', e.target.value)}
                error={Boolean(errors.ttm_profit)}
                helperText={errors.ttm_profit ?? 'What was left after costs. Zero or negative is fine.'}
                fullWidth
                inputMode="decimal"
              />
            </Stack>

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField
                label="Annual growth %"
                value={form.growth_pct}
                onChange={(e) => update('growth_pct', e.target.value)}
                error={Boolean(errors.growth_pct)}
                helperText={errors.growth_pct ?? 'Optional. Revenue growth year on year.'}
                fullWidth
                inputMode="decimal"
              />
              <TextField
                label="Monthly churn %"
                value={form.churn_pct}
                onChange={(e) => update('churn_pct', e.target.value)}
                error={Boolean(errors.churn_pct)}
                helperText={errors.churn_pct ?? 'Optional. Customers lost each month.'}
                fullWidth
                inputMode="decimal"
              />
            </Stack>

            {errors._form && <Alert severity="error">{errors._form}</Alert>}
            {message && <Alert severity="error">{message}</Alert>}

            <Box>
              {/* The label stays "Calculate" throughout — loading is signalled by
                  the spinner, `aria-busy` and the disabled state, not by renaming
                  the control. A button whose accessible name changes mid-action is
                  a moving target for anyone navigating by name, and it is the
                  property U3 pins. */}
              <Button
                type="submit"
                variant="contained"
                size="large"
                disabled={loading}
                aria-busy={loading}
                startIcon={loading ? <CircularProgress size={16} color="inherit" /> : undefined}
              >
                Calculate
              </Button>
              {loading && (
                <Typography role="status" variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Working out your range…
                </Typography>
              )}
            </Box>
          </Stack>
        </Box>
      </Card>

      {/* U7 — before the first submit there is no result block at all. A
          rendered "$0 – $0" would look like an answer, and the answer it looks
          like is "your business is worthless". */}
      {estimate && (
        <Card sx={{ p: { xs: 2.5, sm: 3 }, ...surfaceRecessed }}>
          <Stack spacing={2}>
            <Box>
              <Typography variant="overline" color="text.secondary">
                Estimated range
              </Typography>
              <Typography variant="h4" component="p" sx={{ fontWeight: 600 }}>
                {money(estimate.low)} – {money(estimate.high)}
              </Typography>
            </Box>

            <Typography variant="body1">{estimate.explanation}</Typography>

            <Typography variant="body2" color="text.secondary">
              {estimate.disclaimer}
            </Typography>

            {/* The ask, after the answer. Only ever rendered alongside a result
                — the email field cannot precede the number it refers to. */}
            {captured ? (
              <Alert severity="success">
                Got it — your estimate is on its way, and we&apos;ll be in touch when
                you&apos;re ready to list.
              </Alert>
            ) : (
              <Box component="form" onSubmit={handleCapture} noValidate>
                <Typography variant="subtitle2" gutterBottom>
                  Want this in writing?
                </Typography>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems="flex-start">
                  <TextField
                    label="Email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    error={Boolean(captureError)}
                    helperText={captureError ?? ' '}
                    size="small"
                    fullWidth
                  />
                  <Button
                    type="submit"
                    variant="outlined"
                    disabled={capturing || !email.trim()}
                    sx={{ whiteSpace: 'nowrap', mt: { xs: 0, sm: 0.25 } }}
                  >
                    {capturing ? 'Sending…' : 'Send it to me'}
                  </Button>
                </Stack>
              </Box>
            )}
          </Stack>
        </Card>
      )}
    </Stack>
  )
}
