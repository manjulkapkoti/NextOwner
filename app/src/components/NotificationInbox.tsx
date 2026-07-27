// M8 — the in-app notification inbox (spec 008 J1, J3-J6).
//
// The click-through is a plain route change: the notification carries no
// private content (spec D2), so the destination's own gate decides whether the
// user may actually see anything. A revoked buyer following a stale message
// notification lands on a 403 from the real boundary — the inbox is not, and
// must never become, a second source of authority.
//
// UI Pass 4: the loading state is a row-shaped skeleton (kept `role=
// "progressbar"` on the wrapper so J5's `findByRole('progressbar')` still
// finds it — a skeleton has no implicit ARIA role of its own), the empty
// state uses the shared `EmptyState`, and each row uses the shared
// `PersonRow` instead of a hand-rolled Card — same `data-testid`/
// `data-unread`, same click-to-mark-read-then-navigate behaviour.
import { useEffect } from 'react'
import { Alert, Box, Skeleton, Stack, Typography } from '@mui/material'
import NotificationsNoneOutlined from '@mui/icons-material/NotificationsNoneOutlined'
import { observer } from 'mobx-react-lite'
import { useNavigate } from 'react-router-dom'
import { linkFor, notificationStore } from '../stores/notificationStore'
import { EmptyState } from './EmptyState'
import { PersonRow } from './PersonRow'
import { blueTint } from '../theme'

function NotificationInboxSkeleton() {
  return (
    <Box role="progressbar" aria-label="Loading notifications">
      <Stack spacing={1.5}>
        {Array.from({ length: 4 }).map((_, i) => (
          <Box key={i} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2, p: 2 }}>
            <Skeleton height={20} width="65%" sx={{ mb: 0.75 }} />
            <Skeleton height={14} width="30%" />
          </Box>
        ))}
      </Stack>
    </Box>
  )
}

export const NotificationInbox = observer(function NotificationInbox() {
  const navigate = useNavigate()

  useEffect(() => {
    void notificationStore.load()
  }, [])

  if (notificationStore.status === 'loading' || notificationStore.status === 'idle') {
    return <NotificationInboxSkeleton />
  }

  if (notificationStore.status === 'error') {
    return (
      <Alert severity="error" role="alert">
        We could not load your notifications.
      </Alert>
    )
  }

  if (notificationStore.notifications.length === 0) {
    return <EmptyState message="No notifications yet." />
  }

  async function open(id: number, unread: boolean, to: string) {
    // Mark first, then navigate — but never let a failed mark-read strand the
    // user on the inbox. The read receipt is a convenience; the navigation is
    // what they asked for.
    if (unread) {
      try {
        await notificationStore.markRead(id)
      } catch {
        /* non-fatal */
      }
    }
    navigate(to)
  }

  return (
    <Stack spacing={1.5}>
      {notificationStore.notifications.map((n) => {
        const unread = n.read_at === null
        return (
          <PersonRow
            key={n.id}
            testId={`notification-${n.id}`}
            dataAttrs={{ 'data-unread': String(unread) }}
            sx={{ borderLeft: unread ? 4 : 0, borderLeftColor: 'primary.main' }}
            avatar={
              <Box
                sx={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  bgcolor: blueTint.wash,
                  color: blueTint.onWash,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <NotificationsNoneOutlined fontSize="small" />
              </Box>
            }
            title={
              <Typography variant="body1" fontWeight={unread ? 600 : 400}>
                {n.title}
              </Typography>
            }
            meta={
              <Typography variant="caption" color="text.secondary">
                {new Date(n.created_at).toLocaleString()}
              </Typography>
            }
            onClick={() => void open(n.id, unread, linkFor(n))}
          />
        )
      })}
    </Stack>
  )
})
