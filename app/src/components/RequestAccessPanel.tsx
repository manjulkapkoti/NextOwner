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
import { Alert, Box, Button, Chip, CircularProgress, Fade, Stack, Typography } from '@mui/material'
import { accessStore } from '../stores/accessStore'
import { authStore } from '../stores/authStore'
import { GatedPanel } from './GatedPanel'
import { NdaModal } from './NdaModal'
import { PrivateSection, type DocumentSummary } from './PrivateSection'

// Plays the fade-in only for users who haven't asked for reduced motion —
// same pattern `theme.ts`'s `cardInteractive` token uses for its hover lift.
// A plain `matchMedia` check (no new dependency) is enough here; there is no
// need to re-check on the fly since a gate only transitions to unlocked once
// per mount.
function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

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
      // The file index, behind the same gate. Without this the data room
      // renders empty however many documents the seller uploaded — the gap the
      // M5 appsec review caught, which the new endpoint alone did not close.
      // Failing here must not re-lock a room the gate already opened, so the
      // index is best-effort: the payload is the access decision, the file list
      // is a detail of it.
      try {
        await accessStore.loadDocuments(listingId)
      } catch {
        /* leave the list empty; the private payload is already authorized */
      }
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
    // The moment access flips from locked to unlocked, play a one-time
    // reveal instead of an instant swap: `in appear` fades in immediately on
    // this branch's first render, which is exactly that moment (the
    // component was rendering a different branch beforehand). `Fade` needs a
    // single child that can hold a ref, hence the wrapping `Box` —
    // `PrivateSection` isn't guaranteed to forward one.
    return (
      <Fade in appear timeout={prefersReducedMotion() ? 0 : 250}>
        <Box>
          <PrivateSection
            listingId={listingId}
            data={accessStore.privateData}
            // Mapped here rather than teaching `PrivateSection` the API's shape:
            // the store speaks the server's language (`original_filename`), the
            // display component speaks a display language (`filename`), and the
            // translation lives at the one seam between them. The `documents` prop
            // still wins when supplied, so a caller can inject its own list.
            documents={
              documents.length > 0
                ? documents
                : accessStore.documents.map((doc) => ({
                    id: doc.id,
                    filename: doc.original_filename,
                  }))
            }
          />
        </Box>
      </Fade>
    )
  }

  if (view === 'pending') {
    return (
      <GatedPanel variant="pending" size="full">
        <Stack spacing={1}>
          <Chip label="Access pending" color="warning" sx={{ alignSelf: 'flex-start' }} />
          <Typography variant="body2" color="text.secondary">
            Your request is with the seller. You will see the private details here once
            they approve it.
          </Typography>
        </Stack>
      </GatedPanel>
    )
  }

  if (view === 'denied') {
    return (
      <GatedPanel variant="denied" size="full">
        <Stack spacing={1}>
          <Chip label="Access closed" sx={{ alignSelf: 'flex-start' }} />
          <Typography variant="body2" color="text.secondary">
            The seller is not sharing this listing&apos;s private details with you.
          </Typography>
        </Stack>
      </GatedPanel>
    )
  }

  // locked — the buyer has never asked, or asked and nothing is outstanding.
  return (
    <GatedPanel variant="locked" size="full" redactedFields={['Company name', 'Website', 'Detailed financials']}>
      <Stack spacing={2}>
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
    </GatedPanel>
  )
})
