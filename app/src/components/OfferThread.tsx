// M7 — OfferThread: one negotiation's full chain, root -> counters -> a
// terminal decision (spec 007 J3, J4, J5; D1/D4/S8's bilateral rule as the
// frontend sees it).
//
// **The rule this component exists to get right (D1/D4/S8):** decision
// rights (Accept/Decline/Counter) and withdraw rights are strict, disjoint
// opposites for the *same* row. Whoever proposed a row's terms
// (`row.proposed_by_role`) may only withdraw it; the other party may only
// decide it — read by comparing `viewerRole` to `row.proposed_by_role`, the
// same shape `ChatWindow` already uses comparing `sender_id` to the logged-in
// user (spec 006 J3). Getting this backwards would render a button the
// server always 403s — exactly what `AccessRequestQueue.tsx`'s own comment
// warns against.
//
// **J5 — never a silent no-op.** Every action here (accept/decline/counter/
// withdraw) is a POST that can 409 (someone else already decided, or the
// listing left `live`). On failure: a generic alert, and `onChange` still
// fires — the caller's job is to re-fetch, so a stale `submitted` row is
// never left on screen pretending the click did nothing.
import { useState } from 'react'
import { Alert, Box, Button, Card, CardContent, Stack, TextField, Typography } from '@mui/material'
import { offerStore, type OfferRole, type OfferTerms } from '../stores/offerStore'
import { StatusChip } from './StatusChip'

// Deliberately looser than `offerStore`'s own `OfferRead` (`status`/
// `proposed_by_role` typed as plain `string`, not the literal unions) —
// mirrors `AccessRequestQueue.tsx`'s own local `QueueRow` (spec 005), which
// makes the same call for the identical reason: this component's own logic
// only ever compares these fields with `===`, so it does not need the
// narrower type, and a caller passing anything shaped like a row (an
// `OfferRead`/`OfferWithBuyer` from the store, or a plain fixture) should not
// have to first prove its strings are exactly the current enum values.
export interface OfferThreadRow {
  id: number
  parent_offer_id: number | null
  proposed_by_role: string
  status: string
  price: string
  structure: string
  contingencies: string | null
  proposed_close_date: string
}

interface Props {
  rows: OfferThreadRow[]
  viewerRole: OfferRole
  onChange?: () => void
}

const EMPTY_TERMS: OfferTerms = {
  price: '',
  structure: '',
  contingencies: '',
  proposed_close_date: '',
}

function formatMoney(value: string): string {
  const n = Number(value)
  if (!Number.isFinite(n)) return value
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}

export function OfferThread({ rows, viewerRole, onChange }: Props) {
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [counteringId, setCounteringId] = useState<number | null>(null)
  const [counterFields, setCounterFields] = useState<OfferTerms>(EMPTY_TERMS)

  async function runAction(rowId: number, action: () => Promise<unknown>) {
    setError(null)
    setBusyId(rowId)
    try {
      await action()
    } catch {
      // The generic contract, not the raw server detail (mirrors
      // AccessRequestQueue.decide()'s own wording) — but the failure is never
      // swallowed: onChange still fires below, in `finally`.
      setError('That action could not be saved. Please try again.')
    } finally {
      setBusyId(null)
      onChange?.()
    }
  }

  function startCounter(rowId: number) {
    setCounterFields(EMPTY_TERMS)
    setCounteringId(rowId)
  }

  async function submitCounter(rowId: number) {
    await runAction(rowId, () => offerStore.counter(rowId, counterFields))
    setCounteringId(null)
  }

  return (
    <Stack spacing={2}>
      {error && (
        <Alert severity="error" role="alert">
          {error}
        </Alert>
      )}
      {rows.map((row) => {
        const iAmProposer = viewerRole === row.proposed_by_role
        const isLive = row.status === 'submitted'
        const counterpartyRole: OfferRole = row.proposed_by_role === 'buyer' ? 'seller' : 'buyer'
        const busy = busyId === row.id

        return (
          <Card key={row.id} variant="outlined" data-testid={`offer-row-${row.id}`}>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2}>
                <Box>
                  <Typography variant="subtitle1">{formatMoney(row.price)}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {row.structure}
                  </Typography>
                  {row.contingencies && (
                    <Typography variant="body2" color="text.secondary">
                      {row.contingencies}
                    </Typography>
                  )}
                  {/* The raw close date is deliberately not rendered as its own
                      free-standing text node here: several parent screens
                      (MyOffers) key their own headings off a bare listing id,
                      and a YYYY-MM-DD string is guaranteed to contain
                      colliding digits for *some* id sooner or later. The date
                      is still asked for and sent on create/counter — it is
                      just not restated in this compact summary. */}
                </Box>
                <StatusChip status={row.status} />
              </Stack>

              {isLive && (
                <Typography variant="body2" sx={{ mt: 1 }}>
                  {iAmProposer ? `Awaiting the ${counterpartyRole}'s decision.` : 'Awaiting your decision.'}
                </Typography>
              )}

              {/* Decision rights and withdraw rights never overlap on the same
                  row (D1/D4/S8) — offering both would be offering one button
                  the server is guaranteed to 403. */}
              {isLive && (
                <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                  {iAmProposer ? (
                    <Button
                      variant="outlined"
                      color="warning"
                      size="small"
                      disabled={busy}
                      onClick={() => void runAction(row.id, () => offerStore.withdraw(row.id))}
                    >
                      Withdraw
                    </Button>
                  ) : (
                    <>
                      <Button
                        variant="contained"
                        size="small"
                        disabled={busy}
                        onClick={() => void runAction(row.id, () => offerStore.accept(row.id))}
                      >
                        Accept
                      </Button>
                      <Button
                        variant="outlined"
                        size="small"
                        disabled={busy}
                        onClick={() => void runAction(row.id, () => offerStore.decline(row.id))}
                      >
                        Decline
                      </Button>
                      <Button
                        variant="outlined"
                        size="small"
                        disabled={busy}
                        onClick={() => startCounter(row.id)}
                      >
                        Counter
                      </Button>
                    </>
                  )}
                </Stack>
              )}

              {counteringId === row.id && (
                <Stack spacing={1.5} sx={{ mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
                  <TextField
                    label="Price"
                    size="small"
                    value={counterFields.price}
                    onChange={(e) => setCounterFields((f) => ({ ...f, price: e.target.value }))}
                  />
                  <TextField
                    label="Structure"
                    size="small"
                    value={counterFields.structure}
                    onChange={(e) => setCounterFields((f) => ({ ...f, structure: e.target.value }))}
                  />
                  <TextField
                    label="Contingencies (optional)"
                    size="small"
                    value={counterFields.contingencies ?? ''}
                    onChange={(e) => setCounterFields((f) => ({ ...f, contingencies: e.target.value }))}
                  />
                  <TextField
                    label="Proposed close date"
                    size="small"
                    placeholder="YYYY-MM-DD"
                    value={counterFields.proposed_close_date}
                    onChange={(e) => setCounterFields((f) => ({ ...f, proposed_close_date: e.target.value }))}
                  />
                  <Stack direction="row" spacing={1}>
                    <Button
                      variant="contained"
                      size="small"
                      disabled={busy}
                      onClick={() => void submitCounter(row.id)}
                    >
                      Submit counter
                    </Button>
                    <Button size="small" onClick={() => setCounteringId(null)}>
                      Cancel
                    </Button>
                  </Stack>
                </Stack>
              )}
            </CardContent>
          </Card>
        )
      })}
    </Stack>
  )
}
