// The listing status vocabulary, in one component so the language is
// identical everywhere it appears (docs/design_system_spec.md §6).
//
// Every chip is a light fill with dark text on it — never white on a
// saturated colour — which is what keeps the brighter status hues legible
// (each pair measures >=5.3:1). And every chip carries a *label*: the design
// system's "never colour alone" rule means the colour is reinforcement, not
// the message.
import { Box } from '@mui/material'
import { badge } from '../theme'

// The server's listing state machine. Unknown values fall back to neutral
// rather than crashing, so a new backend status degrades to a plain chip.
//
// M10 adds the buyer-verification vocabulary (`unverified`/`pending`/
// `verified`/`rejected` — spec 010 D1). `rejected` is shared verbatim with the
// listing state machine below: both mean the same thing ("reviewed and
// refused," red), and the two domains never render side by side, so one key
// safely serves both rather than inventing `verification_rejected`. `pending`
// is a new key (listings use `pending_review`, not `pending`), so there is no
// collision to resolve there either.
const STATUS: Record<string, { label: string; tone: keyof typeof badge }> = {
  draft: { label: 'Draft', tone: 'neutral' },
  pending_review: { label: 'In review', tone: 'pending' },
  live: { label: 'Live', tone: 'verified' },
  paused: { label: 'Paused', tone: 'neutral' },
  under_offer: { label: 'Under offer', tone: 'underOffer' },
  sold: { label: 'Sold', tone: 'premium' },
  rejected: { label: 'Rejected', tone: 'rejected' },
  unverified: { label: 'Unverified', tone: 'neutral' },
  pending: { label: 'Pending review', tone: 'pending' },
  verified: { label: 'Verified', tone: 'verified' },
}

export function StatusChip({ status, showDot = false }: { status: string; showDot?: boolean }) {
  const meta = STATUS[status] ?? { label: status, tone: 'neutral' as const }
  const { bg, fg } = badge[meta.tone]

  return (
    <Box
      component="span"
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        px: 1.25,
        py: 0.375,
        borderRadius: 8 / 8,
        bgcolor: bg,
        color: fg,
        fontSize: '0.75rem',
        fontWeight: 600,
        lineHeight: 1.4,
        whiteSpace: 'nowrap',
      }}
    >
      {/* Opt-in (UI Pass 4): a dense queue row (PersonRow) can wire this in to
          help scan-by-colour; every existing call site is unaffected since
          this defaults to false. */}
      {showDot && (
        <Box
          component="span"
          aria-hidden
          sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: fg, mr: 0.75, flexShrink: 0 }}
        />
      )}
      {meta.label}
    </Box>
  )
}
