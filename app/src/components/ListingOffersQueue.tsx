// M7 — the seller's per-listing offers queue (spec 007 J3, FR-17, G1-G4).
//
// Mirrors `AccessRequestQueue.tsx`'s own framing (M5): the seller sees enough
// to decide and nothing more. Here that means every buyer's full negotiation
// thread (root offer -> counters -> the current state), each carrying that
// buyer's profile — but never their email (PII minimization; the backend's
// own G3 already keeps `OfferWithBuyer` from carrying one, this component is
// the "and the UI doesn't invent a place to show one either" companion).
//
// **Grouping.** Each thread is one negotiation: a root offer (`parent_offer_id
// === null`) plus every row descended from it via the `parent_offer_id`
// chain (D1) — which already segments buyers from each other, since a
// counter only ever links back into the negotiation it belongs to. Grouping
// falls back to `buyer_id` when the row carries one (the real API response,
// G1) so two separate historical threads from the same buyer render as one
// section rather than two.
import { useCallback, useEffect, useState } from 'react'
import { observer } from 'mobx-react-lite'
import { Alert, Box, CircularProgress, Stack, Typography } from '@mui/material'
import { offerStore, type OfferWithBuyer } from '../stores/offerStore'
import { OfferThread } from './OfferThread'

interface Props {
  listingId: number
}

function formatBudget(budget: string | number | null): string | null {
  if (budget === null || budget === '') return null
  const value = Number(budget)
  return Number.isFinite(value) ? value.toLocaleString('en-US') : String(budget)
}

function formatIndustries(industries: string | string[] | null): string | null {
  if (!industries) return null
  return Array.isArray(industries) ? industries.join(', ') : industries
}

function chainRootId(row: OfferWithBuyer, byId: Map<number, OfferWithBuyer>): number {
  let current = row
  while (current.parent_offer_id != null) {
    const parent = byId.get(current.parent_offer_id)
    if (!parent) break
    current = parent
  }
  return current.id
}

function groupThreads(rows: OfferWithBuyer[]): Array<{ key: string; rows: OfferWithBuyer[] }> {
  const byId = new Map(rows.map((r) => [r.id, r]))
  const order: string[] = []
  const groups = new Map<string, OfferWithBuyer[]>()

  for (const row of rows) {
    const key = row.buyer_id != null ? `buyer:${row.buyer_id}` : `chain:${chainRootId(row, byId)}`
    if (!groups.has(key)) {
      groups.set(key, [])
      order.push(key)
    }
    groups.get(key)!.push(row)
  }

  return order.map((key) => ({
    key,
    rows: groups.get(key)!.slice().sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at)),
  }))
}

export const ListingOffersQueue = observer(function ListingOffersQueue({ listingId }: Props) {
  const [status, setStatus] = useState<'loading' | 'ready' | 'errored'>('loading')

  const load = useCallback(async () => {
    try {
      await offerStore.loadListingOffers(listingId)
      setStatus('ready')
    } catch {
      setStatus('errored')
    }
  }, [listingId])

  useEffect(() => {
    void load()
  }, [load])

  if (status === 'loading') {
    return (
      <Box sx={{ py: 3, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress aria-label="Loading offers" size={28} />
      </Box>
    )
  }

  if (status === 'errored') {
    return (
      <Alert severity="error" role="alert">
        We could not load the offers for this listing.
      </Alert>
    )
  }

  const rows = offerStore.listingOffers
  const threads = groupThreads(rows)

  if (threads.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
        No offers yet for this listing.
      </Typography>
    )
  }

  return (
    <Stack spacing={4}>
      {threads.map((thread) => {
        const buyer = thread.rows[0].buyer
        const budget = formatBudget(buyer.budget)
        const industries = formatIndustries(buyer.target_industries)
        return (
          <Box key={thread.key}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              {buyer.display_name ?? 'Unnamed buyer'}
            </Typography>
            {budget && (
              <Typography variant="body2" color="text.secondary">
                Budget: {budget}
              </Typography>
            )}
            {/* Industries + experience share one text node deliberately: an
                industry tag ("saas") and free-text experience ("...two SaaS
                exits") can share a substring, and two separate elements each
                independently matching a loose text query is what breaks a
                caller's `getByText` — the same reason this file keeps them in
                one paragraph rather than two adjacent ones. */}
            {(industries || buyer.experience) && (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                {industries}
                {industries && buyer.experience ? ' — ' : ''}
                {buyer.experience}
              </Typography>
            )}
            <OfferThread
              rows={thread.rows}
              viewerRole="seller"
              onChange={() => void offerStore.loadListingOffers(listingId)}
            />
          </Box>
        )
      })}
    </Stack>
  )
})
