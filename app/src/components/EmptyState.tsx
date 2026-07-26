// A shared empty-state primitive, using the `surfaceRecessed` sx token
// (theme.ts, UI Pass 1) so every empty list in the app reads identically.
//
// This will later replace ~8 bare-`Typography` empty states across the app
// (ConversationList, MyOffers, NotificationInbox, SavedSearches, Watchlist,
// etc.) -- not touched in this pass, just built so a later pass can import it.
import { Box, Button, Typography } from '@mui/material'
import { surfaceRecessed } from '../theme'

export interface EmptyStateAction {
  label: string
  onClick: () => void
}

export interface EmptyStateProps {
  message: string
  action?: EmptyStateAction
}

export function EmptyState({ message, action }: EmptyStateProps) {
  return (
    <Box
      sx={{
        ...surfaceRecessed,
        py: 6,
        px: 3,
        textAlign: 'center',
      }}
    >
      <Typography variant="body2" color="text.secondary">
        {message}
      </Typography>
      {action && (
        <Button variant="outlined" onClick={action.onClick} sx={{ mt: 2 }}>
          {action.label}
        </Button>
      )}
    </Box>
  )
}
