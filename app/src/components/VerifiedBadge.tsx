// M10 — the verified-buyer badge (spec 010 D7, FR-14, requirements.md §3
// "verified-buyer badges"). Wherever a `BuyerProfile` is rendered — today
// `AccessRequestQueue.tsx` and, through it, `PersonRow.tsx` — this is the one
// visible signal a seller gets about who is asking.
//
// Deliberately renders nothing unless `verified` is true, rather than a
// four-state chip (unverified/pending/rejected all read as "no badge" here):
// a badge is an affirmative claim, and showing "Rejected" or "Unverified" next
// to every ordinary buyer would turn a trust signal into noise. This also
// makes the anti-staleness property (spec 010 S11 — a revoke must not leave a
// seller looking at a badge that no longer means anything) trivially true: the
// badge simply disappears the moment `verified` flips to false, because there
// is no other branch that renders it.
//
// Builds on `StatusChip` rather than a new one-off chip (StatusChip.tsx
// already carries the `verified` tone/label M10 added there) — "reuse the
// design system, invent nothing."
import { StatusChip } from './StatusChip'

export interface VerifiedBadgeProps {
  /** The computed boolean from `BuyerProfile`/`UserRead` (D7) — never the raw
   * `verification_status` string, so a caller cannot accidentally show a
   * badge for `pending`/`rejected` by passing the wrong thing. */
  verified: boolean
}

export function VerifiedBadge({ verified }: VerifiedBadgeProps) {
  if (!verified) return null
  return <StatusChip status="verified" />
}
