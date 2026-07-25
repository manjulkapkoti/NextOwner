// M7 — the buyer's offer panel on the listing detail page (spec 007 J1, J2,
// X4). Rendered only once the buyer already has approved private access — the
// parent (`ListingDetail`) decides that, exactly like `RequestAccessPanel`
// decides when to render `PrivateSection`.
//
// **State source (the RequestAccessPanel/J2 lesson, spec 005):** the panel's
// state is read on mount from `GET /api/my/offers` via
// `offerStore.loadMyOffers()` + `offerStore.offersForListing(listingId)` —
// never inferred only from a POST response held in local state. A returning
// buyer must see their real offer status on reload, not a stale "make an
// offer" button inviting a 409 `offer_already_active` (A7/D7).
//
// **X4's eight states all live here**, because this component IS "the offer
// panel" X4 names: loading / no-offer-yet / submitted (mine) /
// awaiting-my-decision / accepted / declined / withdrawn / errored. Once any
// row exists for this listing, rendering is delegated to `OfferThread`
// (mirrors `RequestAccessPanel` delegating to `PrivateSection`) — the
// "current" row is whichever one is still `submitted` (at most one, D7), or,
// once the whole chain is terminal, the most recently created row; either way
// that is just "the last row in `offersForListing`'s oldest-first order".
import { useEffect, useState, type FormEvent } from 'react'
import { observer } from 'mobx-react-lite'
import { Alert, Box, Button, CircularProgress, Stack, TextField } from '@mui/material'
import { offerStore, type OfferTerms } from '../stores/offerStore'
import { OfferThread } from './OfferThread'

interface Props {
  listingId: number
}

type Status = 'loading' | 'ready' | 'errored'

const EMPTY_TERMS: OfferTerms = {
  price: '',
  structure: '',
  contingencies: '',
  proposed_close_date: '',
}

export const OfferForm = observer(function OfferForm({ listingId }: Props) {
  const [status, setStatus] = useState<Status>('loading')
  const [fields, setFields] = useState<OfferTerms>(EMPTY_TERMS)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    offerStore
      .loadMyOffers()
      .then(() => {
        if (!cancelled) setStatus('ready')
      })
      .catch(() => {
        if (!cancelled) setStatus('errored')
      })
    return () => {
      cancelled = true
    }
  }, [listingId])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setSubmitError(null)
    try {
      await offerStore.createOffer(listingId, {
        ...fields,
        contingencies: fields.contingencies?.trim() ? fields.contingencies : null,
      })
      setFields(EMPTY_TERMS)
    } catch {
      setSubmitError('Your offer could not be submitted. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (status === 'loading') {
    return (
      <Box sx={{ py: 3, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress aria-label="Checking your offer status" size={28} />
      </Box>
    )
  }

  if (status === 'errored') {
    return (
      <Alert severity="error" role="alert" sx={{ my: 2 }}>
        We could not check your offer status. Please try again.
      </Alert>
    )
  }

  const rows = offerStore.offersForListing(listingId)

  // J2 — an active offer (or its whole, now-terminal chain) replaces the
  // form; never rendered side by side with it.
  if (rows.length > 0) {
    return (
      <OfferThread
        rows={rows}
        viewerRole="buyer"
        onChange={() => void offerStore.loadMyOffers()}
      />
    )
  }

  // J1 — no-offer-yet: the create form.
  return (
    <Box
      component="form"
      onSubmit={onSubmit}
      noValidate
      sx={{ display: 'flex', flexDirection: 'column', gap: 2, my: 2 }}
    >
      {submitError && (
        <Alert severity="error" role="alert">
          {submitError}
        </Alert>
      )}
      <TextField
        label="Price"
        required
        value={fields.price}
        onChange={(e) => setFields((f) => ({ ...f, price: e.target.value }))}
      />
      <TextField
        label="Structure"
        required
        placeholder="e.g. all cash, 70/30 seller financing"
        value={fields.structure}
        onChange={(e) => setFields((f) => ({ ...f, structure: e.target.value }))}
      />
      <TextField
        label="Contingencies (optional)"
        multiline
        minRows={2}
        value={fields.contingencies ?? ''}
        onChange={(e) => setFields((f) => ({ ...f, contingencies: e.target.value }))}
      />
      <TextField
        label="Proposed close date"
        required
        placeholder="YYYY-MM-DD"
        value={fields.proposed_close_date}
        onChange={(e) => setFields((f) => ({ ...f, proposed_close_date: e.target.value }))}
      />
      <Stack direction="row">
        <Button type="submit" variant="contained" disabled={submitting} sx={{ alignSelf: 'flex-start' }}>
          {submitting ? 'Submitting…' : 'Make an offer'}
        </Button>
      </Stack>
    </Box>
  )
})
