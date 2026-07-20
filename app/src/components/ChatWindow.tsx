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
import { useEffect, useState } from 'react'
import { Alert, Box, Button, CircularProgress, Stack, TextField, Typography } from '@mui/material'
import { observer } from 'mobx-react-lite'
import { chatStore } from '../stores/chatStore'
import { authStore } from '../stores/authStore'

interface Props {
  conversationId: number
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
    return (
      <Box sx={{ py: 3, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress aria-label="Loading" size={28} />
      </Box>
    )
  }

  return (
    <Box>
      {chatStore.closeReason && <Alert severity="warning" sx={{ mb: 2 }}>{chatStore.closeReason}</Alert>}

      {chatStore.messages.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
          No messages yet — say hello.
        </Typography>
      ) : (
        <Stack spacing={1} sx={{ mb: 2 }}>
          {chatStore.messages.map((message) => {
            const mine = message.sender_id === authStore.user?.id
            return (
              <Typography
                key={message.id}
                data-testid={mine ? 'message-mine' : 'message-theirs'}
                sx={{
                  alignSelf: mine ? 'flex-end' : 'flex-start',
                  bgcolor: mine ? 'primary.main' : 'action.hover',
                  color: mine ? 'primary.contrastText' : 'text.primary',
                  px: 1.5,
                  py: 0.75,
                  borderRadius: 2,
                  maxWidth: '75%',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {message.text}
              </Typography>
            )
          })}
        </Stack>
      )}

      <Box component="form" onSubmit={submit} sx={{ display: 'flex', gap: 1 }}>
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
