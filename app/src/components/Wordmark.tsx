// The NextOwner logo, in one place so every surface renders it identically.
//
// Two forms of the same identity:
//   "full" — the wordmark ("Next" navy + "Owner" orange, the O being the mark)
//   "mark" — the ring alone, for widths too narrow for the wordmark
//
// Raster, not vector: no SVG source exists yet. Both assets are ~5x the size
// they render at, so they stay sharp on high-DPI screens, and the white
// backgrounds of the originals have been converted to real transparency so
// they sit on any surface. Swap these two imports for SVGs when vector
// artwork arrives — nothing else needs to change.
import { Box } from '@mui/material'
import markSrc from '../assets/mark.png'
import wordmarkSrc from '../assets/wordmark.png'

// Intrinsic aspect ratios, so a height is all a caller ever has to pass.
const WORDMARK_RATIO = 552 / 100
const MARK_RATIO = 88 / 87

type Props = {
  /** Rendered height in px. Width follows from the artwork's aspect ratio. */
  height?: number
  variant?: 'full' | 'mark'
}

export function Wordmark({ height = 24, variant = 'full' }: Props) {
  const isMark = variant === 'mark'
  return (
    <Box
      component="img"
      src={isMark ? markSrc : wordmarkSrc}
      alt="NextOwner"
      sx={{
        display: 'block',
        height,
        width: height * (isMark ? MARK_RATIO : WORDMARK_RATIO),
        // Never let a flex parent squash the logo out of proportion.
        flexShrink: 0,
        userSelect: 'none',
      }}
    />
  )
}
