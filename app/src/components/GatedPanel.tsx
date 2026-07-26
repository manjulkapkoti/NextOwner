// UI Pass 3 (trust-gate consolidation) — the one shared "gated" visual
// treatment (a lock icon in a tinted circle + a recessed surface), previously
// built three separate times: `ListingCard`'s `LockedStrip`,
// `ListingDetail`'s `AnonymousGateCard`, and `RequestAccessPanel`'s
// `GateCard`. All three were visually consistent but structurally
// duplicated, and only two of the three redacted-field placeholder rows
// carried real field labels (`RequestAccessPanel`'s had none at all).
//
// This component is presentation only. It renders whatever `children` the
// caller supplies (unchanged copy, unchanged buttons, unchanged modals) next
// to the lock icon, and — when `redactedFields` is supplied — a row per
// field with the field's real name as accessible text and a decorative,
// `aria-hidden` blurred bar standing in for "a value would be here."
//
// It never renders an `unlocked` state — that stays `PrivateSection`'s own
// (deliberately different, green) treatment. See `RequestAccessPanel.tsx`.
import { Box, Card, Stack, Typography } from '@mui/material'
import type { ReactNode } from 'react'
import LockOutlinedIcon from '@mui/icons-material/LockOutlined'
import { blueTint, surfaceRecessed } from '../theme'

export interface GatedPanelProps {
  variant: 'locked' | 'pending' | 'denied'
  /** compact: 24px icon circle (embedded card context) / full: 32px (page-level). Default 'full'. */
  size?: 'compact' | 'full'
  /** Field labels to tease as redacted rows, e.g. ['Company name', 'Website']. Omit for pending/denied. */
  redactedFields?: string[]
  children: ReactNode
}

const SIZES = {
  compact: { circle: 24, iconFontSize: 14, padding: 1.5, contentSpacing: 0.75 },
  full: { circle: 32, iconFontSize: undefined, padding: 3, contentSpacing: 1 },
} as const

export function GatedPanel({ variant, size = 'full', redactedFields, children }: GatedPanelProps) {
  const dims = SIZES[size]
  const hasRedactedFields = Boolean(redactedFields && redactedFields.length > 0)

  return (
    <Card data-gated-variant={variant} sx={{ ...surfaceRecessed, p: dims.padding, boxShadow: 'none' }}>
      <Stack direction="row" spacing={1.5} alignItems="flex-start">
        <Box
          sx={{
            width: dims.circle,
            height: dims.circle,
            borderRadius: '50%',
            bgcolor: blueTint.wash,
            color: blueTint.onWash,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          {size === 'compact' ? (
            <LockOutlinedIcon sx={{ fontSize: dims.iconFontSize }} />
          ) : (
            <LockOutlinedIcon fontSize="small" />
          )}
        </Box>
        <Stack spacing={dims.contentSpacing} sx={{ flex: 1, minWidth: 0 }}>
          {children}
          {hasRedactedFields && (
            <Stack spacing={0.75}>
              {redactedFields!.map((field) => (
                <Stack key={field} direction="row" spacing={1} alignItems="center">
                  <Typography variant="caption" color="text.secondary">
                    {field}
                  </Typography>
                  {/* Decorative only — the label above is the accessible content. */}
                  <Box
                    aria-hidden
                    sx={{
                      height: 8,
                      width: 60,
                      borderRadius: 1,
                      bgcolor: blueTint.placeholder,
                      filter: 'blur(5px)',
                      opacity: 0.7,
                      flexShrink: 0,
                    }}
                  />
                </Stack>
              ))}
            </Stack>
          )}
        </Stack>
      </Stack>
    </Card>
  )
}
