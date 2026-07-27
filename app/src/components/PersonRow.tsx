// UI Pass 4 — the shared "person row" pattern: an identity element, a title,
// an optional meta line (or several), an optional status chip, and optional
// actions. This shape repeats — with small per-screen variations — across
// `AccessRequestQueue`, `ConversationList`, and `NotificationInbox`, each of
// which previously hand-rolled its own Card/CardContent/Stack tree. Built
// once so those three share one layout implementation rather than three
// slightly different copies (mirrors `GatedPanel`'s own consolidation, UI
// Pass 3).
//
// `title`/`meta` are typed `ReactNode`, not `string`: NotificationInbox needs
// its own font-weight on the title (bold while unread), and
// AccessRequestQueue's meta is several stacked lines (budget, industries,
// experience), not one. PersonRow owns the row's *layout* only — never the
// content's typography or copy, which stays exactly what each caller already
// rendered before this consolidation.
import type { ReactNode } from 'react'
import { Box, Card, CardActionArea, CardContent, Stack } from '@mui/material'
import type { SxProps, Theme } from '@mui/material/styles'

export interface PersonRowProps {
  /** An identity element — an Avatar, an icon-in-a-circle, or similar. */
  avatar: ReactNode
  /** The row's primary line — usually a name or a headline. */
  title: ReactNode
  /** A secondary line (or several stacked lines) — date, status text, profile detail. */
  meta?: ReactNode
  /** A status chip or unread badge, shown at the row's trailing edge. */
  chip?: ReactNode
  /** Action buttons, rendered in their own row below the meta line. */
  actions?: ReactNode
  /** Makes the whole row clickable by wrapping it in a `CardActionArea`. */
  onClick?: () => void
  sx?: SxProps<Theme>
  /** Forwarded to the outer `Card` as `data-testid` — several callers key
   * their tests off a stable per-row id (mirrors `OfferThread`'s own
   * `data-testid="offer-row-{id}"` convention). */
  testId?: string
  /** Any other `data-*` attribute a caller's tests depend on verbatim (e.g.
   * NotificationInbox's `data-unread`). */
  dataAttrs?: Record<string, string>
}

export function PersonRow({
  avatar,
  title,
  meta,
  chip,
  actions,
  onClick,
  sx,
  testId,
  dataAttrs,
}: PersonRowProps) {
  const body = (
    <CardContent>
      <Stack direction="row" spacing={2} alignItems="flex-start">
        <Box sx={{ flexShrink: 0 }}>{avatar}</Box>
        <Stack spacing={0.5} sx={{ flex: 1, minWidth: 0 }}>
          <Stack direction="row" spacing={1.5} alignItems="center" justifyContent="space-between">
            <Box sx={{ minWidth: 0, overflowWrap: 'anywhere' }}>{title}</Box>
            {chip && <Box sx={{ flexShrink: 0 }}>{chip}</Box>}
          </Stack>
          {meta && <Stack spacing={0.25}>{meta}</Stack>}
          {actions && (
            <Stack direction="row" spacing={1} sx={{ pt: 0.5 }}>
              {actions}
            </Stack>
          )}
        </Stack>
      </Stack>
    </CardContent>
  )

  return (
    <Card variant="outlined" data-testid={testId} sx={sx} {...dataAttrs}>
      {onClick ? <CardActionArea onClick={onClick}>{body}</CardActionArea> : body}
    </Card>
  )
}
