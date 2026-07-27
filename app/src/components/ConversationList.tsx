// M6 — the conversation list, the hub for chat entry (spec 006 J2, D5).
//
// D5: no per-listing/per-request deep link exists into a specific
// conversation this milestone — this list (reached via the nav badge) is
// the one place every conversation is reachable from.
//
// UI Pass 4: the loading state is a row-shaped skeleton rather than a bare
// spinner, the empty state uses the shared `EmptyState`, and each row uses
// the shared `PersonRow` (avatar/title/meta/chip) instead of a hand-rolled
// Card/Stack tree — same text, same click target, same unread badge.
import { useEffect, useState } from 'react'
import { Alert, Avatar, Box, Card, CardContent, Skeleton, Stack, Typography } from '@mui/material'
import { observer } from 'mobx-react-lite'
import { useNavigate } from 'react-router-dom'
import { chatStore } from '../stores/chatStore'
import { EmptyState } from './EmptyState'
import { PersonRow } from './PersonRow'
import { blueTint } from '../theme'

function ConversationListSkeleton() {
  return (
    <Stack spacing={1.5} role="status" aria-label="Loading conversations">
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i} variant="outlined">
          <CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2}>
              <Box sx={{ flex: 1 }}>
                <Skeleton height={20} width="55%" sx={{ mb: 0.75 }} />
                <Skeleton height={16} width="35%" />
              </Box>
              <Skeleton variant="circular" width={24} height={24} />
            </Stack>
          </CardContent>
        </Card>
      ))}
    </Stack>
  )
}

export const ConversationList = observer(function ConversationList() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    chatStore
      .loadConversations()
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <ConversationListSkeleton />
  }

  if (error) {
    return (
      <Alert severity="error" role="alert">
        We could not load your conversations.
      </Alert>
    )
  }

  if (chatStore.conversations.length === 0) {
    return <EmptyState message="No conversations yet." />
  }

  return (
    <Stack spacing={1.5}>
      {chatStore.conversations.map((row) => (
        <PersonRow
          key={row.id}
          avatar={
            <Avatar sx={{ bgcolor: blueTint.wash, color: blueTint.onWash, fontWeight: 700 }}>
              {(row.counterpart_display_name ?? row.listing_headline).charAt(0).toUpperCase()}
            </Avatar>
          }
          title={<Typography variant="subtitle1">{row.listing_headline}</Typography>}
          meta={
            row.counterpart_display_name && (
              <Typography variant="body2" color="text.secondary">
                {row.counterpart_display_name}
              </Typography>
            )
          }
          chip={
            row.unread_count > 0 && (
              <Box
                aria-label={`${row.unread_count} unread`}
                sx={{
                  minWidth: 24,
                  height: 24,
                  px: 0.75,
                  borderRadius: 999,
                  bgcolor: 'primary.main',
                  color: 'primary.contrastText',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                }}
              >
                {row.unread_count}
              </Box>
            )
          }
          onClick={() => navigate(`/messages/${row.id}`)}
        />
      ))}
    </Stack>
  )
})
