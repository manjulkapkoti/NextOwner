// M5 — the data room, once the gate has opened (spec 005 J3, FR-15).
//
// Two things here are security, not presentation:
//
//  1. **`website_url` is seller-supplied text.** React escapes it as *content*,
//     but an `href` is not content — `javascript:alert(1)` in an href executes
//     on click. So the scheme is checked against a whitelist before it is ever
//     put in an href (`security.md` §1.4 / XSS-safe render).
//  2. **Documents are fetched, not linked.** The download route is permission-
//     checked and needs the JWT in an Authorization header; a bare `<a href>`
//     sends no header, so it would 401 for everyone. Fetching the blob and
//     handing it to the browser is what makes a *gated* file downloadable.
import { useState } from 'react'
import { Alert, Button, Divider, Link, Stack, Typography } from '@mui/material'
import LockOpenOutlined from '@mui/icons-material/LockOpenOutlined'
import type { ListingPrivate } from '../stores/accessStore'
import { badge } from '../theme'
import { SpotlightCard } from './SpotlightCard'

export interface DocumentSummary {
  id: number
  filename: string
}

interface Props {
  listingId: number
  // Only the fields this component displays. `listing_id` is deliberately not
  // required: it arrives on the payload but the component already takes
  // `listingId` as a prop, and asking for it twice would let the two disagree.
  data: Pick<ListingPrivate, 'company_name' | 'website_url' | 'detailed_financials'>
  documents: DocumentSummary[]
}

/** Only http(s) may reach an href. Anything else renders as inert text. */
function safeHref(url: string): string | null {
  try {
    const parsed = new URL(url, window.location.origin)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? url : null
  } catch {
    return null
  }
}

export function PrivateSection({ listingId, data, documents }: Props) {
  const [error, setError] = useState<string | null>(null)
  const href = safeHref(data.website_url)

  async function download(doc: DocumentSummary) {
    setError(null)
    try {
      const res = await fetch(`/api/listings/${listingId}/documents/${doc.id}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token') ?? ''}` },
      })
      if (!res.ok) throw new Error('download failed')
      const blob = await res.blob()
      const objectUrl = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = objectUrl
      anchor.download = doc.filename
      anchor.click()
      URL.revokeObjectURL(objectUrl)
    } catch {
      setError('That document could not be downloaded just now.')
    }
  }

  return (
    // UI Pass 3 (Part B3) — the payoff/unlocked state. Deliberately GREEN
    // (badge.verified), never the blue lock treatment used on the anonymous/
    // locked gate cards elsewhere: this must read as visually distinct from
    // those, not similar to them.
    <SpotlightCard
      icon={<LockOpenOutlined sx={{ fontSize: 22 }} />}
      tagBg={badge.verified.bg}
      tagIconColor={badge.verified.fg}
      eyebrow="DATA ROOM · ACCESS GRANTED"
      heading={data.company_name}
      points={[]}
      checkBullets={false}
    >
      {href ? (
        <Link href={href} target="_blank" rel="noopener noreferrer">
          {data.website_url}
        </Link>
      ) : (
        // Deliberately not a link: the scheme is not one we will execute.
        <Typography variant="body2" color="text.secondary">
          {data.website_url}
        </Typography>
      )}

      {data.detailed_financials && (
        <Typography variant="body2" sx={{ mt: 2 }}>
          {data.detailed_financials}
        </Typography>
      )}

      {/* Notes, not bullets — a check mark here would read as "verified,"
          which is not the claim being made. */}
      <Stack spacing={0.75} sx={{ mt: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Everything on this page is covered by the NDA you signed.
        </Typography>
        <Typography variant="body2" color="text.secondary">
          The seller can withdraw this access at any time.
        </Typography>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      )}

      {documents.length > 0 && (
        <>
          <Divider sx={{ mt: 3, mb: 2 }} />
          <Stack spacing={1}>
            <Typography variant="subtitle2">Documents</Typography>
            {documents.map((doc) => (
              <Button
                key={doc.id}
                variant="outlined"
                size="small"
                sx={{ alignSelf: 'flex-start' }}
                onClick={() => download(doc)}
              >
                {doc.filename}
              </Button>
            ))}
          </Stack>
        </>
      )}
    </SpotlightCard>
  )
}
