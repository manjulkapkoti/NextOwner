// M8 — the in-app notification inbox (spec 008 J1, J3-J6).
//
// The click-through is a plain route change: the notification carries no
// private content (spec D2), so the destination's own gate decides whether the
// user may actually see anything. A revoked buyer following a stale message
// notification lands on a 403 from the real boundary — the inbox is not, and
// must never become, a second source of authority.
import { useEffect } from 'react'
import {
  Alert,
  Box,
  Card,
  CardActionArea,
  CardContent,
  CircularProgress,
  Stack,
  Typography,
} from '@mui/material'
import { observer } from 'mobx-react-lite'
import { useNavigate } from 'react-router-dom'
import { linkFor, notificationStore } from '../stores/notificationStore'

export const NotificationInbox = observer(function NotificationInbox() {
  const navigate = useNavigate()

  useEffect(() => {
    void notificationStore.load()
  }, [])

  if (notificationStore.status === 'loading' || notificationStore.status === 'idle') {
    return (
      <Box sx={{ py: 3, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress aria-label="Loading notifications" size={28} />
      </Box>
    )
  }

  if (notificationStore.status === 'error') {
    return (
      <Alert severity="error" role="alert">
        We could not load your notifications.
      </Alert>
    )
  }

  if (notificationStore.notifications.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
        No notifications yet.
      </Typography>
    )
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
          <Card
            key={n.id}
            data-testid={`notification-${n.id}`}
            data-unread={String(unread)}
            variant="outlined"
            sx={{ borderLeft: unread ? 4 : 0, borderLeftColor: 'primary.main' }}
          >
            <CardActionArea onClick={() => void open(n.id, unread, linkFor(n))}>
              <CardContent>
                <Typography variant="body1" fontWeight={unread ? 600 : 400}>
                  {n.title}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {new Date(n.created_at).toLocaleString()}
                </Typography>
              </CardContent>
            </CardActionArea>
          </Card>
        )
      })}
    </Stack>
  )
})
