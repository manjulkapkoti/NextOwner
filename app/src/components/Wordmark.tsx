// The NextOwner logo, in one place so every surface renders it identically.
//
// TWO EXPRESSIONS, NEVER BOTH AT ONCE:
//   default    — the wordmark: "Next" in blue, the ring as the "O", "wner" in
//                orange. This is the artwork as drawn (docs/brand/title.png),
//                where the ring *is* the O.
//   iconOnly   — the app-icon tile, for widths too narrow for the wordmark.
//
// The tile used to sit beside the wordmark, which put the ring on screen twice
// — once in the tile, once as the O — so the mark competed with itself. They
// are alternatives now, which is also why the tile can return on small screens
// without reintroducing that duplication.
//
// "Next" and "wner" are live text, not an image of text, so the wordmark stays
// crisp at any size, scales with the type system, and can be recoloured for
// dark mode. Only the ring and the tile are artwork.
import { Box, Typography } from '@mui/material'
import iconSrc from '../assets/logo-icon.png'
import ringSrc from '../assets/ring.png'
import { logoColors } from '../theme'

// The wordmark is set in Manrope — the display face — not Inter, which runs
// the UI. A logo in the same face as the surrounding buttons reads as a
// heading rather than a mark, and Manrope's rounder, more geometric bowls are
// closer kin to the ring that replaces the O.
const WORDMARK_FONT = '"Manrope", "Inter", sans-serif'

// The ring stands in for a capital O, so its geometry is derived from two
// measured facts rather than eyeballed:
//
//   RING_TO_CAP   from the artwork (docs/brand/title.png): cap 68px, ring
//                 78px. Round glyphs are overshot so they don't read small
//                 beside flat-topped letters like N and W.
//   CAP_HEIGHT_EM from the font binary's OS/2 table (Manrope 800: capHeight
//                 1440 / unitsPerEm 2000). It is face-specific — Inter is
//                 0.7275em — so it must be re-read, never carried across.
//
// ALIGNMENT: the ring is anchored to the BASELINE, not centred in the line
// box. Line-box centring depends on half-leading, which varies with every
// face's ascent/descent, and it left the ring sitting ~1px high in Manrope.
// The baseline is also the thing the eye actually compares against. A real
// capital O sits on the baseline and overshoots below it by half the total
// overshoot, so the ring does the same.
const RING_TO_CAP = 78 / 68
const CAP_HEIGHT_EM = 0.72
const RING_EM = CAP_HEIGHT_EM * RING_TO_CAP // ~0.826em
const OVERSHOOT_EM = ((RING_TO_CAP - 1) / 2) * CAP_HEIGHT_EM // ~0.053em below baseline

type Props = {
  /** Wordmark type size in px; the ring is sized from it. */
  fontSize?: number
  /** Tile size in px, used only by `iconOnly`. */
  iconSize?: number
  /** Show the tile instead of the wordmark — for narrow widths. */
  iconOnly?: boolean
}

export function Wordmark({ fontSize = 30, iconSize = 30, iconOnly = false }: Props) {
  if (iconOnly) {
    return (
      <Box
        role="img"
        aria-label="NextOwner"
        component="img"
        src={iconSrc}
        alt=""
        sx={{
          display: 'block',
          width: iconSize,
          height: iconSize,
          flexShrink: 0,
          // The tile artwork is a full square; the corners are rounded here.
          borderRadius: `${Math.round(iconSize * 0.24)}px`,
        }}
      />
    )
  }

  const ringSize = fontSize * RING_EM
  const overshoot = fontSize * OVERSHOOT_EM

  return (
    <Typography
      // One accessible name for the lockup: unlabelled it would announce as
      // "Next", an image, then "wner" — and "wner" is not a word.
      role="img"
      aria-label="NextOwner"
      component="span"
      sx={{
        display: 'inline-flex',
        // Baseline, not centre — see the alignment note above.
        alignItems: 'baseline',
        fontFamily: WORDMARK_FONT,
        fontWeight: 800,
        letterSpacing: '-0.022em',
        // lineHeight 1 makes the line box exactly 1em, which centres cap
        // height within it — so centring the ring aligns it with the
        // capitals either side.
        lineHeight: 1,
        fontSize,
        whiteSpace: 'nowrap',
        userSelect: 'none',
        flexShrink: 0,
      }}
    >
      <Box aria-hidden component="span" sx={{ color: logoColors.wordmarkNext }}>
        Next
      </Box>
      <Box
        aria-hidden
        component="img"
        src={ringSrc}
        alt=""
        sx={{
          display: 'block',
          height: ringSize,
          width: ringSize,
          flexShrink: 0,
          // `align-items: baseline` puts an image's bottom edge on the
          // baseline; this nudges it down by the overshoot, so it sits exactly
          // where a real capital O would. Relative offset, so it shifts
          // visually without changing the lockup's layout height.
          position: 'relative',
          top: `${overshoot}px`,
          // Side bearings measured from the artwork (10px before the ring,
          // 6px after, against a 68px cap), less what the neighbouring glyphs
          // already carry in their own bearings.
          ml: `${fontSize * 0.05}px`,
          mr: `${fontSize * 0.02}px`,
        }}
      />
      <Box aria-hidden component="span" sx={{ color: logoColors.orange }}>
        wner
      </Box>
    </Typography>
  )
}
