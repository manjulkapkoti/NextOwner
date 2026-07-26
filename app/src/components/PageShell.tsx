// Shared page-frame primitives (UI Pass 1, 2026-07-26).
//
// `App.tsx` currently repeats the same page-frame block (a `Container` plus a
// title/subtitle/action row) inline at every screen. These two components
// give that block one home so later passes can wire it in without
// reinventing the spacing each time. Nothing consumes them yet -- see
// docs/design_system_spec.md's Pass 1 note.
import type { ReactNode } from 'react'
import { Box, Container, Typography } from '@mui/material'
import type { ContainerProps } from '@mui/material'

export function PageContainer({
  children,
  maxWidth = 'md',
  sx,
  ...rest
}: ContainerProps) {
  return (
    <Container
      maxWidth={maxWidth}
      sx={{ pt: { xs: 4, md: 6 }, pb: { xs: 8, md: 12 }, ...sx }}
      {...rest}
    >
      {children}
    </Container>
  )
}

export interface PageHeaderProps {
  title: string
  subtitle?: string
  action?: ReactNode
}

export function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  return (
    <Box sx={{ mb: { xs: 3, md: 4 } }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 2,
        }}
      >
        <Typography variant="h3">{title}</Typography>
        {action}
      </Box>
      {subtitle && (
        <Typography variant="body1" color="text.secondary" sx={{ maxWidth: '60ch', mt: 1 }}>
          {subtitle}
        </Typography>
      )}
    </Box>
  )
}
