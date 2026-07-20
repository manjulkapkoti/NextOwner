// M5 — the buyer's view of the gate on a listing (spec 005 J1, J2, J3, J5, X4).
//
// Turns the gate's outcomes into the four states plan.md names: locked /
// pending / approved / denied.
//
// **Where the state comes from matters.** It is read on mount from
// `GET /api/my/access-requests` (the buyer's own rows, filtered to this
// listing) — *not* only from the POST response of a request made in this
// session. A POST response knows nothing about a request made last week, so a
// POST-only design shows a returning buyer the "Request access" button for a
// request they already made, and clicking it earns a 409 (B3). `GET private`
// is still the actual gate; the list only says whether it is worth calling.
//
// **J5 is the sharp edge.** `api.ts` clears the token and fires
// `auth:unauthorized` on 401. A 403 `nda_access_required` is the *normal*
// outcome of not being approved yet — treating it as a session failure would
// bounce a logged-in buyer to /login. `accessStore` keeps that distinction; the
// only thing this component must not do is re-introduce it.
import { useCallback, useEffect, useState } from 'react'
import { observer } from 'mobx-react-lite'
import { Alert, Box, Button, Chip, CircularProgress, Stack, Typography } from '@mui/material'
import { accessStore } from '../stores/accessStore'
import { authStore } from '../stores/authStore'
import { NdaModal } from './NdaModal'
import { PrivateSection, type DocumentSummary } from './PrivateSection'

interface Props {
  listingId: number
  documents?: DocumentSummary[]
}

type View = 'loading' | 'locked' | 'pending' | 'denied' | 'unlocked' | 'error'

export const RequestAccessPanel = observer(function RequestAccessPanel({
  listingId,
  documents = [],
}: Props) {
  const [view, setView] = useState<View>('loading')
  const [modalOpen, setModalOpen] = useState(false)

  const refresh = useCallback(async () => {
    setView('loading')
    try {
      await accessStore.loadMyRequests()
    } catch {
      setView('error')
      return
    }

    const row = accessStore.requestFor(listingId)
    // `denied` and `revoked` are terminal (spec D3) — the buyer cannot ask
    // again, so showing them a Request access button would be a lie.
    if (row?.status === 'denied' || row?.status === 'revoked') {
      setView('denied')
      return
    }

    try {
      await accessStore.loadPrivate(listingId)
      setView('unlocked')
    } catch {
      // A 403 is the gate working. Which locked state to show depends on
      // whether a request is already outstanding.
      if (accessStore.status === 'locked') {
        setView(row?.status === 'requested' ? 'pending' : 'locked')
      } else {
        setView('error')
      }
    }
  }, [listingId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  async function onRequestClick() {
    // The NDA is signed once, ever — so the modal appears only for a buyer who
    // has not signed. A signed buyer goes straight through (J2).
    if (!authStore.user?.nda_signed_at) {
      setModalOpen(true)
      return
    }
    try {
      await accessStore.requestAccess(listingId)
      setView('pending')
    } catch {
      setView('error')
    }
  }

  if (view === 'loading') {
    return (
      <Box sx={{ py: 3, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress aria-label="Checking your access" size={28} />
      </Box>
    )
  }

  if (view === 'error') {
    return (
      <Alert severity="error" role="alert" sx={{ my: 2 }}>
        We could not check your access to this listing. Please try again.
      </Alert>
    )
  }

  if (view === 'unlocked' && accessStore.privateData) {
    return (
      <PrivateSection
        listingId={listingId}
        data={accessStore.privateData}
        documents={documents}
      />
    )
  }

  if (view === 'pending') {
    return (
      <Stack spacing={1} sx={{ my: 2 }}>
        <Chip label="Access pending" color="warning" sx={{ alignSelf: 'flex-start' }} />
        <Typography variant="body2" color="text.secondary">
          Your request is with the seller. You will see the private details here once
          they approve it.
        </Typography>
      </Stack>
    )
  }

  if (view === 'denied') {
    return (
      <Stack spacing={1} sx={{ my: 2 }}>
        <Chip label="Access closed" sx={{ alignSelf: 'flex-start' }} />
        <Typography variant="body2" color="text.secondary">
          The seller is not sharing this listing&apos;s private details with you.
        </Typography>
      </Stack>
    )
  }

  // locked — the buyer has never asked, or asked and nothing is outstanding.
  return (
    <Stack spacing={2} sx={{ my: 2 }}>
      <Typography variant="body2" color="text.secondary">
        The seller shares real financials, the company name and the data room with
        buyers they approve.
      </Typography>
      <Button variant="contained" sx={{ alignSelf: 'flex-start' }} onClick={onRequestClick}>
        Request access
      </Button>
      <NdaModal
        open={modalOpen}
        listingId={listingId}
        onClose={() => setModalOpen(false)}
        onSigned={() => {
          setModalOpen(false)
          setView('pending')
        }}
      />
    </Stack>
  )
})
