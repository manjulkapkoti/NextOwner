// M6 — the chat window: history + the live socket (spec 006 J3, J4, J5, X2, X3).
//
// Two things here are security, not presentation, mirroring PrivateSection's
// own framing (M5):
//  1. Messages render as **text** — `{m.text}` inside a `Typography`, never
//     `dangerouslySetInnerHTML`. React's default escaping is the control (J4).
//  2. "Mine" vs "theirs" is decided by comparing `sender_id` to the caller's
//     own id from `authStore`, never trusted from anything the payload
//     labels itself — there is nothing to label; the server never sends a
//     "you" flag, on purpose.
//
// UI Pass 4: asymmetric bubble corners distinguish mine/theirs, a capped
// bubble width keeps a long message from stretching the full container, a
// consolidated timestamp shows only when the sender changes or a >5-minute
// gap opens (not one per message), and the composer is pinned to the bottom
// of a fixed-height, independently-scrolling message list rather than
// growing the page. None of this touches the socket connection, the send
// logic, or any existing test id.
import { useEffect, useState } from 'react'
import { Alert, Box, Button, Skeleton, Stack, TextField, Typography } from '@mui/material'
import { observer } from 'mobx-react-lite'
import { chatStore, type ChatMessage } from '../stores/chatStore'
import { authStore } from '../stores/authStore'
import { EmptyState } from './EmptyState'
import { surfaceRecessed } from '../theme'

interface Props {
  conversationId: number
}

const TIMESTAMP_GAP_MS = 5 * 60 * 1000

// A timestamp shows above a message only when the sender changed or the gap
// since the previous message exceeds the threshold — not one per message.
function shouldShowTimestamp(messages: ChatMessage[], index: number): boolean {
  if (index === 0) return true
  const prev = messages[index - 1]
  const curr = messages[index]
  if (prev.sender_id !== curr.sender_id) return true
  return Date.parse(curr.created_at) - Date.parse(prev.created_at) > TIMESTAMP_GAP_MS
}

function ChatWindowSkeleton() {
  const widths = ['55%', '40%', '65%', '35%']
  return (
    <Stack spacing={1.5} sx={{ py: 1 }} role="status" aria-label="Loading conversation">
      {widths.map((w, i) => (
        <Skeleton
          key={i}
          height={40}
          width={w}
          sx={{ alignSelf: i % 2 === 0 ? 'flex-start' : 'flex-end' }}
        />
      ))}
    </Stack>
  )
}

export const ChatWindow = observer(function ChatWindow({ conversationId }: Props) {
  const [text, setText] = useState('')
  const [historyLoaded, setHistoryLoaded] = useState(false)

  useEffect(() => {
    chatStore.reset()
    chatStore
      .loadHistory(conversationId)
      .catch(() => {})
      .finally(() => setHistoryLoaded(true))
    void chatStore.markRead(conversationId)
    chatStore.connect(conversationId)
    return () => chatStore.disconnect()
  }, [conversationId])

  // "Updated when the window is open" (design_implementation.md M6): every
  // new message that arrives while this component is mounted marks the
  // conversation read again, not only on the initial mount.
  const messageCount = chatStore.messages.length
  useEffect(() => {
    if (messageCount > 0) {
      void chatStore.markRead(conversationId)
    }
  }, [messageCount, conversationId])

  function submit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = text.trim()
    if (!trimmed) return
    chatStore.send(trimmed)
    setText('')
  }

  if (!historyLoaded) {
    return <ChatWindowSkeleton />
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: { xs: '60vh', sm: '65vh' }, minHeight: 360 }}>
      {chatStore.closeReason && <Alert severity="warning" sx={{ mb: 2 }}>{chatStore.closeReason}</Alert>}

      <Box sx={{ flex: 1, overflowY: 'auto', pr: 0.5 }}>
        {chatStore.messages.length === 0 ? (
          <EmptyState message="No messages yet — say hello." />
        ) : (
          <Stack spacing={0.5} sx={{ pb: 1 }}>
            {chatStore.messages.map((message, index) => {
              const mine = message.sender_id === authStore.user?.id
              const showTimestamp = shouldShowTimestamp(chatStore.messages, index)
              return (
                <Box key={message.id} sx={{ display: 'flex', flexDirection: 'column', alignItems: mine ? 'flex-end' : 'flex-start' }}>
                  {showTimestamp && (
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, mb: 0.25, px: 0.5 }}>
                      {new Date(message.created_at).toLocaleString()}
                    </Typography>
                  )}
                  <Typography
                    data-testid={mine ? 'message-mine' : 'message-theirs'}
                    sx={{
                      bgcolor: mine ? 'primary.main' : surfaceRecessed.backgroundColor,
                      color: mine ? 'primary.contrastText' : 'text.primary',
                      border: mine ? 'none' : surfaceRecessed.border,
                      px: 1.5,
                      py: 0.75,
                      // Asymmetric corners: the "sent" side gets one squared
                      // corner so mine/theirs read as distinct bubble shapes,
                      // not just a colour swap.
                      borderRadius: mine ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                      maxWidth: { xs: '85%', sm: '70%' },
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {message.text}
                  </Typography>
                </Box>
              )
            })}
          </Stack>
        )}
      </Box>

      <Box
        component="form"
        onSubmit={submit}
        sx={{
          display: 'flex',
          gap: 1,
          pt: 1.5,
          mt: 1,
          position: 'sticky',
          bottom: 0,
          bgcolor: 'background.paper',
          borderTop: '1px solid',
          borderColor: 'divider',
        }}
      >
        <TextField
          fullWidth
          size="small"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type a message"
        />
        <Button type="submit" variant="contained">
          Send
        </Button>
      </Box>
    </Box>
  )
})
