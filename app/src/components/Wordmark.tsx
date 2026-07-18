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

// Ring geometry, measured from the master artwork (docs/brand/title.png)
// rather than eyeballed: there, cap height is 68px and the ring is 78px, so
// the ring runs 1.15x cap height — the overshoot that stops a round glyph
// reading small beside flat-topped letters like N and W.
//
// The asset is cropped to the ring's exact bounds, which matters: CSS sizes
// the canvas, not the ink, so padding baked into the image would silently
// shrink the mark (it did — the previous asset was 38% padding, rendering
// the ring at about half the size it should have been).
const RING_TO_CAP = 78 / 68
const INTER_CAP_HEIGHT_EM = 0.727
const RING_EM = INTER_CAP_HEIGHT_EM * RING_TO_CAP // ≈ 0.834em
const RING_RATIO = 78 / 78

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
              // Side bearings, so the ring sits in the word like a letter.
              // Asymmetric because the artwork is: 10px before the ring, 6px
              // after, against a 68px cap. The adjacent glyphs carry some of
              // that in their own bearings, so only the remainder is added.
              ml: `${fontSize * 0.05}px`,
              mr: `${fontSize * 0.02}px`,
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
