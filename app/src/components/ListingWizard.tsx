// M2 — the seller's multi-step listing builder (spec H1; FR-5).
// MUI Stepper: basics → metrics → private → review. Each step validates before
// it advances; the final step POSTs to /listings. Money is entered as strings
// and sent as-is (the server parses Decimal).
//
// Presentation follows design_system_spec.md: one card, a step header naming
// what this step is for, and money/metric fields set in tabular figures so
// digits line up. Validation and submission behaviour are unchanged.
import { useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  Divider,
  MenuItem,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from '@mui/material'
import RateReviewOutlined from '@mui/icons-material/RateReviewOutlined'
import { api } from '../lib/api'
import { SpotlightCard } from './SpotlightCard'
import { tabularNums } from '../theme'

// UI Pass 3 (Part B2) — "what happens next," shown above the review step's
// field readback.
const REVIEW_SPOTLIGHT_POINTS = [
  'This saves a private draft. You can keep editing it, and nobody else can see it.',
  'When you submit it, it goes to review — going live is a decision, not a delay.',
  'Once live, buyers see the metrics. The company name and detailed financials only reach buyers you approve.',
]

const STEPS = ['Basics', 'Metrics', 'Private', 'Review']

// What each step is for, said once at the top of it rather than left implicit.
//
// The Metrics line used to read "Leave anything you do not have blank", which
// contradicted the schema it was describing (spec 013 F4/D12): `ListingCreate`
// requires all five of these, and a blank field serialises to "" which fails
// Decimal validation — so following the wizard's own instruction produced a
// 422. Fixed on the UI side rather than by making five columns nullable, which
// would ripple into M4's filters, M11's valuation inputs and every response
// model that reads them, to fix a sentence. Zero is also the more accurate
// datum: "this business has no MRR" is a fact worth storing as 0, not as absent.
const STEP_BLURB = [
  'The headline buyers see first, and what you want for the business.',
  'The numbers buyers screen on. All five are required — enter 0 where one does not apply.',
  'Only shared with buyers you approve — never shown publicly.',
  'Check it over. This creates a private draft; nothing goes live yet.',
]

// The listing-type vocabulary (spec 013 F3/D12). `Listing.type` is free text on
// the server, so this list is the product's vocabulary rather than a schema
// constraint — which is exactly why it must match what already exists instead
// of being invented here. These five are the values `seed/seed.py` writes and
// the ones M11's valuation whitelist names; M4's browse filter is an equality
// match, so a sixth value invented here would be a type no buyer could filter
// for and no seeded listing would sit beside.
const BUSINESS_TYPES: Array<[value: string, label: string]> = [
  ['saas', 'SaaS'],
  ['ecommerce', 'E-commerce'],
  ['content', 'Content / media'],
  ['marketplace', 'Marketplace'],
  ['agency', 'Agency / services'],
]

// The five `ListingCreate` requires with no default, and the reason step 1 now
// marks them required (F4). `description`, `company_name` and `headline` are
// required too, but they are strings where "" is merely empty rather than
// invalid — these five are the ones that 422.
const METRIC_FIELDS: Array<[label: string, key: string]> = [
  ['TTM revenue', 'ttm_revenue'],
  ['TTM profit', 'ttm_profit'],
  ['MRR', 'mrr'],
  ['Churn %', 'churn_pct'],
  ['Customers', 'customers'],
]

type Form = Record<string, string>

const EMPTY: Form = {
  type: '',
  headline: '',
  asking_price: '',
  ttm_revenue: '',
  ttm_profit: '',
  mrr: '',
  churn_pct: '',
  customers: '',
  company_name: '',
  website_url: '',
  description: '',
  detailed_financials: '',
}

// The review step reads back what was entered, so the last screen before
// submit is a check rather than a promise that you checked.
const REVIEW_FIELDS: Array<[label: string, key: string]> = [
  ['Headline', 'headline'],
  ['Asking price', 'asking_price'],
  ['TTM revenue', 'ttm_revenue'],
  ['TTM profit', 'ttm_profit'],
  ['MRR', 'mrr'],
  ['Company name', 'company_name'],
  ['Website', 'website_url'],
]

export function ListingWizard() {
  const [step, setStep] = useState(0)
  const [form, setForm] = useState<Form>(EMPTY)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  // Widened from ChangeEvent<HTMLInputElement> so the same helper serves the
  // Select on step 0, whose change event carries a different element type.
  const set = (name: string) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [name]: e.target.value }))

  function validateStep(): boolean {
    const next: Record<string, string> = {}
    if (step === 0) {
      if (!form.headline.trim()) next.headline = 'A headline is required'
      if (!(Number(form.asking_price) > 0)) next.asking_price = 'Asking price must be greater than 0'
      // Not cosmetic: M4's browse filter is `Listing.type == query.type`, so a
      // listing created without one can never match a type filter (F3).
      if (!form.type) next.type = 'Choose the type that fits best'
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  function onNext() {
    if (!validateStep()) return
    setStep((s) => Math.min(s + 1, STEPS.length - 1))
  }

  async function onSubmit() {
    setSubmitError(null)
    try {
      await api('/listings', { method: 'POST', body: JSON.stringify(form) })
      setDone(true)
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : 'Could not create the listing')
    }
  }

  if (done) return <Alert severity="success">Draft created.</Alert>

  const fieldStack = { display: 'flex', flexDirection: 'column', gap: 2.5 } as const

  return (
    <Box sx={{ maxWidth: 680, mx: 'auto' }}>
      <Typography variant="h4" component="h1" sx={{ mb: 3 }}>
        List a business
      </Typography>

      <Card sx={{ p: { xs: 3, sm: 4 } }}>
        <Stepper activeStep={step} sx={{ mb: 4 }}>
          {STEPS.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          {STEP_BLURB[step]}
        </Typography>

        {step === 0 && (
          <Box sx={fieldStack}>
            <TextField
              label="Headline"
              fullWidth
              value={form.headline}
              onChange={set('headline')}
              error={Boolean(errors.headline)}
              helperText={errors.headline || 'e.g. "Profitable B2B SaaS in the HR space"'}
            />
            <TextField
              label="Asking price"
              fullWidth
              value={form.asking_price}
              onChange={set('asking_price')}
              error={Boolean(errors.asking_price)}
              helperText={errors.asking_price}
              inputProps={{ inputMode: 'decimal' }}
              sx={{ '& input': tabularNums }}
            />
            <TextField
              select
              label="Business type"
              fullWidth
              value={form.type}
              onChange={set('type')}
              error={Boolean(errors.type)}
              helperText={errors.type || 'Buyers filter the marketplace by this.'}
            >
              {BUSINESS_TYPES.map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
          </Box>
        )}

        {step === 1 && (
          <Box sx={fieldStack}>
            {METRIC_FIELDS.map(([label, key]) => (
              <TextField
                key={key}
                label={label}
                required
                fullWidth
                value={form[key]}
                onChange={set(key)}
                inputProps={{ inputMode: 'decimal' }}
                sx={{ '& input': tabularNums }}
              />
            ))}
          </Box>
        )}

        {step === 2 && (
          <Box sx={fieldStack}>
            <TextField label="Company name" fullWidth value={form.company_name} onChange={set('company_name')} />
            <TextField label="Website URL" fullWidth value={form.website_url} onChange={set('website_url')} />
            <TextField
              label="Description"
              fullWidth
              multiline
              minRows={4}
              value={form.description}
              onChange={set('description')}
            />
          </Box>
        )}

        {step === 3 && (
          <Box>
            <Box sx={{ mb: 3 }}>
              <SpotlightCard
                variant="inset"
                icon={<RateReviewOutlined sx={{ fontSize: 22, color: 'primary.main' }} />}
                eyebrow="WHAT HAPPENS NEXT"
                heading="Creating a draft is not publishing"
                points={REVIEW_SPOTLIGHT_POINTS}
              />
            </Box>
            {REVIEW_FIELDS.map(([label, key]) => (
              <Box key={key}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, py: 1.25 }}>
                  <Typography variant="body2" color="text.secondary">
                    {label}
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 500, textAlign: 'right', overflowWrap: 'anywhere', ...tabularNums }}
                  >
                    {form[key]?.trim() ? form[key] : '—'}
                  </Typography>
                </Box>
                <Divider />
              </Box>
            ))}
          </Box>
        )}

        {submitError && (
          <Alert severity="error" sx={{ mt: 3 }}>
            {submitError}
          </Alert>
        )}

        <Box sx={{ display: 'flex', gap: 1.5, mt: 4 }}>
          <Button disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
            Back
          </Button>
          <Box sx={{ flexGrow: 1 }} />
          {step < STEPS.length - 1 ? (
            <Button variant="contained" onClick={onNext}>
              Next
            </Button>
          ) : (
            <Button variant="contained" onClick={onSubmit}>
              Create draft
            </Button>
          )}
        </Box>
      </Card>
    </Box>
  )
}
