// M12 — the seller's deal-close actions (spec 012 F1-F7, FR-8).
//
// The two most consequential buttons in the product: one ends a listing's life
// permanently, the other unwinds a deal both parties had agreed. Everything
// here exists to make "irreversible" visible *before* it happens.
//
// **The price is rendered, never entered.** The server derives the recorded
// sale price from the accepted offer (spec 012 D4/S1), so an input here would
// imply a control the seller does not have — and a number the UI let them type
// but the API ignored is worse than no number at all.
//
// **No optimistic update.** The status chip changes only on the server's
// response. An optimistic flip to `sold` that the server then refused would be
// the UI lying about money; the same "re-read from the server rather than
// patching local state" rule `AccessRequestQueue.decide()` follows.
import { useState } from 'react'
import {
  Alert,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Stack,
  Typography,
} from '@mui/material'
import { offerStore } from '../stores/offerStore'
import { ApiError } from '../lib/api'

interface DealListing {
  id: number
  status: string
  headline?: string
  final_price?: string | null
  sold_at?: string | null
}

interface Props {
  listing: DealListing
  /** The accepted offer's price, for display only — the server derives the
   * value it actually records. `null` while it is still loading. */
  acceptedPrice: string | null
  onChange: () => void
}

type Action = 'sold' | 'fell-through'

const COPY: Record<Action, { trigger: string; confirm: string; title: string; body: string }> = {
  sold: {
    trigger: 'Mark as sold',
    confirm: 'Mark as sold',
    title: 'Mark this deal as sold?',
    body:
      'Your listing will be recorded as sold at the accepted offer price and removed from the ' +
      'marketplace. This is final and cannot be undone.',
  },
  'fell-through': {
    trigger: 'Deal fell through',
    confirm: 'Put back on the market',
    title: 'Did this deal fall through?',
    body:
      'The accepted offer will be closed and your listing goes back on the marketplace at its ' +
      'approved terms. Buyers whose offers were declined when you accepted are not restored — ' +
      'they will need to make a new offer.',
  },
}

export function formatPrice(value: string | null): string | null {
  if (value === null || value === '') return null
  const amount = Number(value)
  // Fall back to the raw string rather than rendering `NaN`: the API sends
  // money as an exact decimal string, and a value this cannot parse is a
  // reason to show it verbatim, not to invent one.
  if (!Number.isFinite(amount)) return value
  return amount.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}

export function DealActions({ listing, acceptedPrice, onChange }: Props) {
  const [pending, setPending] = useState<Action | null>(null)
  const [inFlight, setInFlight] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // The whole component is gated on the one state these transitions are legal
  // from (spec 012 F2). The server refuses everything else with a 409 anyway —
  // this is the UX half, not the boundary.
  if (listing.status !== 'under_offer') return null

  const price = formatPrice(acceptedPrice)

  async function run(action: Action) {
    setInFlight(true)
    setError(null)
    try {
      if (action === 'sold') {
        await offerStore.markSold(listing.id)
      } else {
        await offerStore.relist(listing.id)
      }
      setPending(null)
      onChange()
    } catch (err) {
      // The server's own message, through the error contract — never a
      // reworded guess at what went wrong (`docs/error_handling.md` §3).
      setError(
        err instanceof ApiError
          ? err.message
          : 'We could not update this deal. Please try again.',
      )
    } finally {
      setInFlight(false)
    }
  }

  return (
    <Card variant="outlined" sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          This listing is under offer
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          {price
            ? `Closing this deal records a sale price of ${price}, taken from the accepted offer.`
            : 'Closing this deal records the accepted offer’s price as the sale price.'}
        </Typography>

        {/* Only when the dialog is closed — a modal hides everything behind it
            from the accessibility tree, so an error rendered here while the
            confirmation is open would be invisible to a screen reader and
            unreachable by pointer. The open case renders it inside the dialog
            instead, where the seller is actually looking (spec 012 F6). */}
        {error && pending === null && (
          <Alert severity="error" role="alert" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}

        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mt: 2 }}>
          <Button
            variant="contained"
            disabled={inFlight}
            onClick={() => {
              setError(null)
              setPending('sold')
            }}
          >
            {COPY.sold.trigger}
          </Button>
          <Button
            variant="outlined"
            disabled={inFlight}
            onClick={() => {
              setError(null)
              setPending('fell-through')
            }}
          >
            {COPY['fell-through'].trigger}
          </Button>
        </Stack>
      </CardContent>

      <Dialog open={pending !== null} onClose={() => !inFlight && setPending(null)}>
        {pending && (
          <>
            <DialogTitle>{COPY[pending].title}</DialogTitle>
            <DialogContent>
              <DialogContentText>{COPY[pending].body}</DialogContentText>
              {pending === 'sold' && price && (
                <DialogContentText sx={{ mt: 2, fontWeight: 600 }}>
                  Recorded sale price: {price}
                </DialogContentText>
              )}
              {error && (
                <Alert severity="error" role="alert" sx={{ mt: 2 }}>
                  {error}
                </Alert>
              )}
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setPending(null)} disabled={inFlight}>
                Cancel
              </Button>
              <Button
                variant="contained"
                disabled={inFlight}
                onClick={() => void run(pending)}
              >
                {COPY[pending].confirm}
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>
    </Card>
  )
}
