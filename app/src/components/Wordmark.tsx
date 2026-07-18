// The NextOwner logo, in one place so every surface renders it identically.
//
// The lockup is: [icon tile] Next(blue) (ring)wner(orange) — matching the
// supplied artwork, where the "O" of "Owner" is the ring mark.
//
// "Next" and "wner" are live text, not an image of text, so the wordmark
// stays crisp at any size, scales with the type system, and can be recoloured
// for dark mode. Only the tile and the ring are artwork.
import { Box, Typography } from '@mui/material'
import iconSrc from '../assets/logo-icon.png'
import ringSrc from '../assets/ring.png'
import { logoColors } from '../theme'

const RING_RATIO = 88 / 87

// The ring stands in for a capital O, so it is sized against cap height
// (~0.73em in Inter) and set fractionally larger, the way a round glyph is
// optically overshot so it doesn't read as small next to flat-topped letters.
const RING_EM = 0.8

type Props = {
  /** Height of the icon tile in px; the wordmark is sized to match. */
  height?: number
  /** Icon only — for widths too narrow to fit the wordmark beside it. */
  iconOnly?: boolean
}

export function Wordmark({ height = 28, iconOnly = false }: Props) {
  const fontSize = height * 0.82
  const ringSize = fontSize * RING_EM

  return (
    <Box
      // One accessible name for the whole lockup: without this a screen reader
      // announces the tile, "Next", the ring and "wner" as four separate
      // things — and "wner" is not a word.
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
            display: 'inline-flex',
            alignItems: 'center',
            fontWeight: 700,
            letterSpacing: '-0.02em',
            // lineHeight 1 makes the line box exactly 1em, which centres cap
            // height in it — so aligning the ring to centre lines it up with
            // the capitals either side of it.
            lineHeight: 1,
            fontSize,
            whiteSpace: 'nowrap',
            userSelect: 'none',
          }}
        >
          <Box component="span" sx={{ color: logoColors.wordmarkNext }}>
            Next
          </Box>
          <Box
            component="img"
            src={ringSrc}
            alt=""
            sx={{
              display: 'block',
              height: ringSize,
              width: ringSize * RING_RATIO,
              flexShrink: 0,
              // Side bearings, so the ring sits in the word like a letter
              // rather than being jammed against its neighbours.
              mx: `${fontSize * 0.03}px`,
            }}
          />
          <Box component="span" sx={{ color: logoColors.orange }}>
            wner
          </Box>
        </Typography>
      )}
    </Box>
  )
}
