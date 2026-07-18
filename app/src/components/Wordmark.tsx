// The NextOwner logo, in one place so every surface renders it identically.
//
// The icon tile is artwork; "NextOwner" is live text — navy "Next" + orange
// "Owner", matching the supplied lockup. Text rather than an image of text so
// it stays crisp at any size, scales with the type system, can be recoloured
// for dark mode, and is selectable and translatable.
//
// The tile is a full square (no baked-in corner rounding), so the radius is
// applied here in CSS.
import { Box, Typography } from '@mui/material'
import iconSrc from '../assets/logo-icon.png'
import { logoColors } from '../theme'

type Props = {
  /** Height of the icon tile in px; the wordmark is sized to match. */
  height?: number
  /** Icon only — for widths too narrow to fit the wordmark beside it. */
  iconOnly?: boolean
}

export function Wordmark({ height = 28, iconOnly = false }: Props) {
  return (
    <Box
      // One accessible name for the whole lockup: without this, a screen
      // reader would announce the icon and the two text halves separately.
      role="img"
      aria-label="NextOwner"
      sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}
    >
      <Box
        aria-hidden
        component="img"
        src={iconSrc}
        alt=""
        sx={{
          display: 'block',
          width: height,
          height,
          flexShrink: 0,
          borderRadius: `${Math.round(height * 0.24)}px`,
        }}
      />
      {!iconOnly && (
        <Typography
          aria-hidden
          component="span"
          sx={{
            fontWeight: 700,
            letterSpacing: '-0.02em',
            lineHeight: 1,
            fontSize: height * 0.82,
            whiteSpace: 'nowrap',
            userSelect: 'none',
          }}
        >
          <Box component="span" sx={{ color: logoColors.navy }}>
            Next
          </Box>
          <Box component="span" sx={{ color: logoColors.orange }}>
            Owner
          </Box>
        </Typography>
      )}
    </Box>
  )
}
