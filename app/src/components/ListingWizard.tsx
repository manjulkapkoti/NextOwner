// M2 — the seller's multi-step listing builder (spec H1; FR-5).
// MUI Stepper: basics → metrics → private → review. Each step validates before
// it advances; the final step POSTs to /listings. Money is entered as strings
// and sent as-is (the server parses Decimal).
import { useState } from 'react'
import { Alert, Box, Button, Step, StepLabel, Stepper, TextField, Typography } from '@mui/material'
import { api } from '../lib/api'

const STEPS = ['Basics', 'Metrics', 'Private', 'Review']

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

export function ListingWizard() {
  const [step, setStep] = useState(0)
  const [form, setForm] = useState<Form>(EMPTY)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const set = (name: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [name]: e.target.value }))

  function validateStep(): boolean {
    const next: Record<string, string> = {}
    if (step === 0) {
      if (!form.headline.trim()) next.headline = 'A headline is required'
      if (!(Number(form.asking_price) > 0)) next.asking_price = 'Asking price must be greater than 0'
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

  return (
    <Box sx={{ maxWidth: 640 }}>
      <Stepper activeStep={step} sx={{ mb: 3 }}>
        {STEPS.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {step === 0 && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField label="Headline" value={form.headline} onChange={set('headline')}
            error={Boolean(errors.headline)} helperText={errors.headline} />
          <TextField label="Asking price" value={form.asking_price} onChange={set('asking_price')}
            error={Boolean(errors.asking_price)} helperText={errors.asking_price} />
        </Box>
      )}
      {step === 1 && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField label="TTM revenue" value={form.ttm_revenue} onChange={set('ttm_revenue')} />
          <TextField label="TTM profit" value={form.ttm_profit} onChange={set('ttm_profit')} />
          <TextField label="MRR" value={form.mrr} onChange={set('mrr')} />
          <TextField label="Churn %" value={form.churn_pct} onChange={set('churn_pct')} />
          <TextField label="Customers" value={form.customers} onChange={set('customers')} />
        </Box>
      )}
      {step === 2 && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField label="Company name" value={form.company_name} onChange={set('company_name')} />
          <TextField label="Website URL" value={form.website_url} onChange={set('website_url')} />
          <TextField label="Description" multiline value={form.description} onChange={set('description')} />
        </Box>
      )}
      {step === 3 && <Typography>Review your details, then create the draft.</Typography>}

      {submitError && <Alert severity="error" sx={{ mt: 2 }}>{submitError}</Alert>}

      <Box sx={{ display: 'flex', gap: 1, mt: 3 }}>
        <Button disabled={step === 0} onClick={() => setStep((s) => s - 1)}>Back</Button>
        {step < STEPS.length - 1 ? (
          <Button variant="contained" onClick={onNext}>Next</Button>
        ) : (
          <Button variant="contained" onClick={onSubmit}>Create draft</Button>
        )}
      </Box>
    </Box>
  )
}
