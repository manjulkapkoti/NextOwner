// M5 — the click-wrap platform NDA (spec 005 J1, FR-13).
//
// One platform-wide NDA, signed once, ever (Baton-adopted, constitution Article
// 4). The buyer sees this the first time they ask for access anywhere and never
// again — so it is deliberately a modal in the request flow rather than a
// separate page: signing is not the goal, getting access is.
//
// Two API calls, one user gesture, **in order**: sign, then request. The order
// is not cosmetic — the server refuses an access request from an unsigned user
// with 403 `nda_not_signed` (B2), so requesting first would simply fail.
import { useState } from 'react'
import {
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Alert,
  Typography,
} from '@mui/material'
import { accessStore } from '../stores/accessStore'

interface Props {
  open: boolean
  listingId: number
  onClose: () => void
  onSigned: () => void
}

export function NdaModal({ open, listingId, onClose, onSigned }: Props) {
  const [agreed, setAgreed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      await accessStore.signNda()
      await accessStore.requestAccess(listingId)
      onSigned()
    } catch {
      // Generic, client-safe copy — never the server's internals.
      setError('We could not complete that just now. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} aria-labelledby="nda-modal-title" maxWidth="sm" fullWidth>
      <DialogTitle id="nda-modal-title">Non-disclosure agreement</DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ mb: 2 }}>
          Sellers share confidential details — real financials, customer numbers, the
          company name — with buyers they choose. Signing once lets you ask any seller on
          NextOwner for that access. You agree to keep everything you see confidential and
          to use it only to evaluate the business.
        </Typography>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <FormControlLabel
          control={
            <Checkbox checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
          }
          label="I have read and agree to these confidentiality terms."
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>
          Cancel
        </Button>
        {/* Disabled until the box is ticked: a click-wrap signature that could be
            given without the affirmative act is not a signature. */}
        <Button variant="contained" onClick={confirm} disabled={!agreed || busy}>
          Sign and request access
        </Button>
      </DialogActions>
    </Dialog>
  )
}
