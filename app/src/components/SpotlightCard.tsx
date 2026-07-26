// UI Pass 3 — the shared "spotlight card" pattern: an elevated card (or, in
// `variant="inset"`, a plain recessed Box for use *inside* another card, since
// cards must never nest) with a small icon tag overlapping its top edge, an
// eyebrow label, a heading, bullet points, and an optional CTA.
//
// Built once so the landing page's two new cards (Part A) and the four reuse
// spots (Part B: MyListings empty state, ListingWizard review step,
// PrivateSection's unlocked data room, MyOffers empty state) share one
// implementation rather than five copies of the same markup.
import type { ElementType, ReactNode } from 'react'
import { Box, Button, Card, Stack, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import CheckRounded from '@mui/icons-material/CheckRounded'
import { blueTint, elevation, outlinedBrandTint, surfaceRecessed } from '../theme'

export interface SpotlightCardProps {
  icon: ReactNode
  eyebrow: string
  heading: string
  points: string[]
  cta?: { label: string; to: string }
  tagBg?: string
  tagIconColor?: string
  /**
   * `"card"` (default): an elevated `Card` — for standalone use (landing
   * page, empty states). `"inset"`: a plain `Box` with `surfaceRecessed`
   * instead — for use *inside* another component's own outer `Card` (e.g.
   * ListingWizard's review step), where nesting a second `Card` would be
   * wrong.
   */
  variant?: 'card' | 'inset'
  /** Bullet points render with a leading check icon by default. Set to
   * `false` for a spot where a check mark would misleadingly read as
   * "verified" (PrivateSection's unlocked notes). */
  checkBullets?: boolean
  /** Extra content rendered below the points/CTA — e.g. PrivateSection's
   * website link + document list, kept inside the same card. */
  children?: ReactNode
}

export function SpotlightCard({
  icon,
  eyebrow,
  heading,
  points,
  cta,
  tagBg = 'background.paper',
  tagIconColor = 'primary.main',
  variant = 'card',
  checkBullets = true,
  children,
}: SpotlightCardProps) {
  const Container: ElementType = variant === 'inset' ? Box : Card
  const containerSx =
    variant === 'inset'
      ? { ...surfaceRecessed, pt: 5.5, px: 3.5, pb: 3.5, height: '100%' }
      : { pt: 5.5, px: 3.5, pb: 3.5, height: '100%', boxShadow: elevation.brandMd }

  return (
    <Box sx={{ position: 'relative', pt: 3, height: '100%' }}>
      <Box
        aria-hidden
        sx={{
          position: 'absolute',
          top: 0,
          left: 28,
          width: 52,
          height: 52,
          borderRadius: 1.75,
          bgcolor: tagBg,
          border: '1px solid',
          borderColor: blueTint.wellBorder,
          boxShadow: '0 6px 16px rgba(37,99,235,0.12)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 2,
          color: tagIconColor,
        }}
      >
        {icon}
      </Box>
      <Container sx={containerSx}>
        <Typography variant="overline" sx={{ color: blueTint.onWash, display: 'block', mb: 1 }}>
          {eyebrow}
        </Typography>
        <Typography
          variant="h5"
          component="h2"
          sx={{ fontWeight: 700, fontSize: '1.375rem', letterSpacing: '-0.015em', mb: 1.75 }}
        >
          {heading}
        </Typography>
        {points.length > 0 && (
          <Stack component="ul" spacing={1.25} sx={{ listStyle: 'none', m: 0, p: 0, mb: children || cta ? 2.5 : 0 }}>
            {points.map((point) => (
              <Stack component="li" direction="row" spacing={1.25} key={point}>
                {checkBullets && (
                  <CheckRounded aria-hidden sx={{ fontSize: 18, color: 'primary.main', mt: 0.25 }} />
                )}
                <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.55 }}>
                  {point}
                </Typography>
              </Stack>
            ))}
          </Stack>
        )}
        {cta && (
          <Button variant="outlined" component={RouterLink} to={cta.to} sx={{ ...outlinedBrandTint }}>
            {cta.label}
          </Button>
        )}
        {children}
      </Container>
    </Box>
  )
}
