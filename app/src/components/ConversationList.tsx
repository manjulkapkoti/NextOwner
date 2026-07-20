// M6 — the conversation list, the hub for chat entry (spec 006 J2, D5).
//
// D5: no per-listing/per-request deep link exists into a specific
// conversation this milestone — this list (reached via the nav badge) is
// the one place every conversation is reachable from.
import { useEffect, useState } from 'react'
import { Alert, Box, Card, CardActionArea, CardContent, CircularProgress, Stack, Typography } from '@mui/material'
import { observer } from 'mobx-react-lite'
import { useNavigate } from 'react-router-dom'
import { chatStore } from '../stores/chatStore'

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
    return (
      <Box sx={{ py: 3, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress aria-label="Loading conversations" size={28} />
      </Box>
    )
  }

  if (error) {
    return (
      <Alert severity="error" role="alert">
        We could not load your conversations.
      </Alert>
    )
  }

  if (chatStore.conversations.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
        No conversations yet.
      </Typography>
    )
  }

  return (
    <Stack spacing={1.5}>
      {chatStore.conversations.map((row) => (
        <Card key={row.id} variant="outlined">
          <CardActionArea onClick={() => navigate(`/messages/${row.id}`)}>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2}>
                <Box>
                  <Typography variant="subtitle1">{row.listing_headline}</Typography>
                  {row.counterpart_display_name && (
                    <Typography variant="body2" color="text.secondary">
                      {row.counterpart_display_name}
                    </Typography>
                  )}
                </Box>
                {row.unread_count > 0 && (
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
                )}
              </Stack>
            </CardContent>
          </CardActionArea>
        </Card>
      ))}
    </Stack>
  )
})
