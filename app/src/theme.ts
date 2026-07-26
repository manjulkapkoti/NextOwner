// NextOwner MUI theme.
//
// This file holds every literal design value and is the single source of token
// truth; `docs/design_system_spec.md` holds the decisions and their reasons. One job
// each — a value defined in both places is a value that will drift.
//
// Structured as `createAppTheme(mode)` so the dark palette is a fill-in, not a
// rewrite.
//
// Where this deviates from the authored v1 token spec, it is deliberate and
// recorded in design_system_spec.md § Deviations. Every deviation exists because the
// spec's own "WCAG AA contrast" rule contradicted the literal value it gave —
// measured, not guessed.
import { createTheme, alpha } from '@mui/material/styles'
import type { PaletteMode, Shadows, ThemeOptions } from '@mui/material/styles'

// ---------------------------------------------------------------------------
// Raw tokens
// ---------------------------------------------------------------------------

/** Cool-grey (slate) neutral ramp. Matches the token spec exactly. */
export const neutral = {
  0: '#FFFFFF',
  25: '#F8FAFC',
  50: '#F1F5F9',
  100: '#E2E8F0',
  300: '#CBD5E1',
  400: '#94A3B8',
  500: '#64748B',
  600: '#475569',
  700: '#334155',
  800: '#1E293B',
  900: '#0F172A',
} as const

/** Brand blue — trust, primary actions, links, focus. */
export const brand = {
  main: '#2563EB',
  dark: '#1D4ED8', // hover
  darker: '#1E40AF', // active
  light: '#93C5FD',
  contrastText: '#FFFFFF',
} as const

/**
 * Brand orange. Deliberately NOT the CTA colour.
 *
 * The v1 spec contradicted itself here: its token principles say "Orange =
 * emphasis & CTAs" while its component rules say "Buttons — Primary: blue
 * fill". Blue wins, because `#F97316` measures 2.80:1 on white and cannot
 * legally carry white text on a button. Orange is reserved for the logo and
 * the Featured badge, which keeps it from colliding with `warning` amber —
 * a brand accent that reads as "something needs attention" is worse than none.
 */
export const accent = {
  main: '#F97316', // fills and marks only, never text on white
  text: '#C2410C', // 5.18:1 — the readable orange, for text/icons
  tint: '#FFEDD5',
} as const

/** Pale blue wash for selected / hover *surfaces* (not fills of the brand). */
export const brandTint = '#EFF6FF'

/**
 * The logo's own colours, sampled from the artwork (`docs/brand/title.png`).
 * Recorded so nothing re-eyeballs them from a PNG.
 */
export const logoColors = {
  navy: '#0C162B', // the app-icon tile, and the browser theme-color
  orange: '#FF6600', // "Owner" in the wordmark, and the ring mark
  wordmarkNext: brand.main, // "Next" shares the UI primary
} as const

/**
 * Status/badge pairs — a light fill with dark text on it, rather than white
 * on a saturated fill. This is what makes the spec's brighter hues usable:
 * every pair below measures >=5.3:1, where white-on-`#10B981` was 2.54:1.
 *
 * Consumed by StatusChip (M3) for the listing state machine. Pairing each with
 * a *label* is mandatory — the spec's own "don't rely on colour alone".
 */
export const badge = {
  verified: { bg: '#DCFCE7', fg: '#166534' },
  featured: { bg: accent.tint, fg: '#9A3412' },
  premium: { bg: '#EDE9FE', fg: '#6D28D9' },
  pending: { bg: '#FEF3C7', fg: '#92400E' },
  rejected: { bg: '#FEE2E2', fg: '#B91C1C' },
  underOffer: { bg: '#DBEAFE', fg: '#1D4ED8' },
  neutral: { bg: neutral[50], fg: neutral[700] },
} as const

/**
 * UI Pass 3 (Option 2 — "Blue as Environment", 2026-07-26): the audit found
 * page-vs-card contrast at 1.05:1 (visually the same white) and blue confined
 * to button fills. This tints the page/well/wash surfaces themselves so blue
 * reads as the *environment* the product sits in, not just an accent.
 *
 * Hard rule: any text/icon rendered on `wash` (#DBEAFE) MUST use `onWash`
 * (#1D4ED8), never `primary.main`/#2563EB directly — the brighter blue fails
 * AA contrast on that specific background.
 */
export const blueTint = {
  page: '#F5F8FD',
  well: '#EFF4FC',
  wellBorder: '#DCE7F7',
  band: brandTint, // alias — brandTint already exists above, not redeclared
  wash: badge.underOffer.bg, // alias — #DBEAFE already exists as badge.underOffer.bg
  washBorder: '#BFDBFE',
  onWash: brand.dark, // #1D4ED8 — mandatory for text/icon on `wash`, see hard rule above
  placeholder: '#C7DBF7',
} as const

/**
 * Opt-in tabular figures so money/metrics columns align. Spread into `sx` on
 * any element that renders currency or KPIs, e.g. `sx={{ ...tabularNums }}`.
 */
export const tabularNums = { fontVariantNumeric: 'tabular-nums' } as const

/**
 * The narrowest viewport the layout is designed to hold together at (px).
 * Applied as `body { min-width }`, so narrower viewports scroll horizontally
 * rather than wrapping the nav and squeezing form controls.
 */
export const LAYOUT_MIN_WIDTH = 360

/** Motion tokens (token spec § motion). */
export const motion = {
  fast: 150,
  normal: 250,
  slow: 350,
  easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
} as const

/**
 * Minimum touch target (token spec § accessibility). Applied only on coarse
 * pointers: a 44px floor on every small button would bloat the desktop UI,
 * while touch devices are exactly where the guideline matters.
 */
const COARSE_POINTER_TARGET = 44

// ---------------------------------------------------------------------------
// Elevation — the spec's three shadows, mapped onto MUI's 25-step scale
// ---------------------------------------------------------------------------

const SHADOW_RGB = '15, 23, 42' // slate-900, for tinted (not pure-black) shadows
export const elevation = {
  sm: `0 1px 2px rgba(${SHADOW_RGB}, 0.05)`,
  md: `0 4px 12px rgba(${SHADOW_RGB}, 0.08)`,
  lg: `0 12px 24px rgba(${SHADOW_RGB}, 0.12)`,
  // Pass 1 additions (UI design pass, 2026-07-26): a recessed/inset surface
  // (e.g. `surfaceRecessed` below) and a focus/selection ring, both slate- and
  // brand-tinted respectively to match the existing `elevation` convention.
  inset: `inset 0 1px 3px rgba(${SHADOW_RGB}, 0.06)`,
  ring: `0 0 0 1px rgba(37, 99, 235, 0.35)`, // brand.main as RGB
  // UI Pass 3 — used only by the spotlight-card pattern's `Card` and icon-tag
  // `boxShadow` (LandingPage's new spotlight cards + SpotlightCard.tsx).
  brandMd: `0 4px 20px rgba(37, 99, 235, 0.10)`,
} as const

const softShadows = [...createTheme().shadows] as Shadows
softShadows[1] = elevation.sm
softShadows[2] = elevation.sm
softShadows[3] = elevation.md
softShadows[4] = elevation.md
softShadows[6] = elevation.lg
softShadows[8] = elevation.lg
// MUI's Dialog (elevation 24) and Menu/Popover (elevation 8, already mapped
// above -- but Dialog also probes 16 via its Paper) request these indices by
// default. Without a mapping they fall through to MUI's own stock
// high-elevation shadow, which is why dialogs looked like a generic MUI
// dialog rather than this theme's own top tier.
softShadows[16] = elevation.lg
softShadows[24] = elevation.lg

// ---------------------------------------------------------------------------
// Palette — keyed by mode so dark mode is a fill-in, not a rewrite
// ---------------------------------------------------------------------------

function getPalette(mode: PaletteMode): ThemeOptions['palette'] {
  // Semantic `main` values are the AA-passing shades (>=4.5:1 on white), not
  // the spec's literal brighter hues — those measured 2.15-2.77:1 and fail as
  // text or as a filled button. The bright hues survive as the `light` fills
  // in `badge` above, where dark text sits on them.
  const semantic = {
    primary: { main: brand.main, dark: brand.dark, light: brand.light, contrastText: '#FFFFFF' },
    secondary: { main: accent.main, dark: accent.text, light: accent.tint, contrastText: '#FFFFFF' },
    success: { main: '#15803D', light: badge.verified.bg, dark: '#166534', contrastText: '#FFFFFF' },
    warning: { main: '#B45309', light: badge.pending.bg, dark: '#92400E', contrastText: '#FFFFFF' },
    error: { main: '#DC2626', light: badge.rejected.bg, dark: '#B91C1C', contrastText: '#FFFFFF' },
    info: { main: '#0369A1', light: badge.underOffer.bg, dark: '#075985', contrastText: '#FFFFFF' },
    grey: neutral,
  }

  if (mode === 'dark') {
    // Values from the token spec § dark theme. Not yet exercised by any screen.
    return {
      mode,
      ...semantic,
      background: { default: '#020617', paper: neutral[900] },
      text: { primary: neutral[25], secondary: neutral[300], disabled: neutral[500] },
      divider: alpha('#FFFFFF', 0.12),
    }
  }

  return {
    mode,
    ...semantic,
    // UI Pass 3 (Option 2): the page background is now blue-tinted so cards
    // (still `neutral[0]`/white) read as distinct surfaces sitting on it.
    // `divider` stays `neutral[100]` — untouched.
    background: { default: blueTint.page, paper: neutral[0] },
    text: { primary: neutral[900], secondary: neutral[600], disabled: neutral[400] },
    divider: neutral[100],
  }
}

// ---------------------------------------------------------------------------
// Theme factory
// ---------------------------------------------------------------------------

export function createAppTheme(mode: PaletteMode = 'light') {
  const palette = getPalette(mode)
  const isDark = mode === 'dark'

  return createTheme({
    palette,
    // The token spec's 4px grid, kept on MUI's 8px multiplier.
    //
    // DEVIATION IN MECHANISM, NOT OUTCOME: every value on the spec's scale is
    // reachable and lands on a 4px multiple — 4=0.5, 8=1, 12=1.5, 16=2,
    // 20=2.5, 24=3, 32=4, 40=5, 48=6, 64=8, 80=10, 96=12. Setting the
    // multiplier to 4 instead would halve the meaning of every spacing prop
    // already written across the app, changing six screens' layout silently
    // for no visual gain. The grid is what the spec is protecting; this
    // honours it.
    spacing: 8,
    shape: { borderRadius: 8 },
    shadows: softShadows,
    // Token spec § breakpoints. `sm` is the tablet boundary (768), which is
    // where the nav collapses to its menu.
    breakpoints: { values: { xs: 0, sm: 768, md: 1024, lg: 1280, xl: 1536 } },
    transitions: {
      duration: { shortest: motion.fast, short: motion.fast, standard: motion.normal, complex: motion.slow },
      easing: { easeInOut: motion.easing },
    },

    typography: {
      // Manrope for display, Inter for UI (token spec § typography).
      fontFamily:
        '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
      // Sizes and line heights are the spec's, expressed as ratios.
      h1: { fontFamily: '"Manrope", "Inter", sans-serif', fontSize: '3rem', fontWeight: 700, lineHeight: 56 / 48, letterSpacing: '-0.022em' },
      h2: { fontFamily: '"Manrope", "Inter", sans-serif', fontSize: '2.25rem', fontWeight: 700, lineHeight: 44 / 36, letterSpacing: '-0.02em' },
      h3: { fontFamily: '"Manrope", "Inter", sans-serif', fontSize: '1.875rem', fontWeight: 600, lineHeight: 38 / 30, letterSpacing: '-0.018em' },
      h4: { fontFamily: '"Manrope", "Inter", sans-serif', fontSize: '1.5rem', fontWeight: 600, lineHeight: 32 / 24, letterSpacing: '-0.015em' },
      h5: { fontSize: '1.25rem', fontWeight: 600, lineHeight: 28 / 20, letterSpacing: '-0.01em' },
      // The spec stops at H5; H6 continues the ramp at the spec's `lg` size.
      h6: { fontSize: '1.125rem', fontWeight: 600, lineHeight: 26 / 18, letterSpacing: '-0.006em' },
      subtitle1: { fontSize: '1rem', fontWeight: 500, lineHeight: 24 / 16 },
      subtitle2: { fontSize: '0.875rem', fontWeight: 600, lineHeight: 20 / 14 },
      body1: { fontSize: '1rem', lineHeight: 24 / 16, letterSpacing: '-0.002em' },
      body2: { fontSize: '0.875rem', lineHeight: 20 / 14, letterSpacing: '-0.001em' },
      button: { fontWeight: 600, letterSpacing: 0, textTransform: 'none' },
      caption: { fontSize: '0.75rem', lineHeight: 16 / 12, letterSpacing: '0.01em' },
      overline: { fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase' },
    },

    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            WebkitFontSmoothing: 'antialiased',
            MozOsxFontSmoothing: 'grayscale',
            textRendering: 'optimizeLegibility',
            // Layout floor — narrower viewports scroll horizontally rather
            // than wrapping the nav and squeezing form controls. 360px is the
            // narrowest mainstream phone, so this should never be hit in use.
            minWidth: LAYOUT_MIN_WIDTH,
          },
          '::selection': { backgroundColor: alpha(brand.main, 0.16) },
          // The spec's focus ring (#93C5FD) measures 1.80:1 on white, where
          // WCAG 2.2 requires 3:1 for a focus indicator — it would be nearly
          // invisible. The brand blue (5.17:1) is used instead.
          ':focus-visible': {
            outline: `2px solid ${brand.main}`,
            outlineOffset: 2,
          },
        },
      },

      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: {
            borderRadius: 8,
            paddingInline: 18,
            paddingBlock: 8,
            transition: `background-color ${motion.fast}ms ${motion.easing}, box-shadow ${motion.fast}ms ${motion.easing}, border-color ${motion.fast}ms ${motion.easing}`,
            // Token spec § accessibility: 44px minimum touch target, applied
            // where it matters rather than everywhere.
            '@media (pointer: coarse)': { minHeight: COARSE_POINTER_TARGET },
          },
          sizeLarge: { paddingInline: 24, paddingBlock: 11, fontSize: '1rem' },
          sizeSmall: { paddingInline: 12, paddingBlock: 5 },
          containedPrimary: {
            boxShadow: elevation.sm,
            '&:hover': { backgroundColor: brand.dark, boxShadow: elevation.md },
            '&:active': { backgroundColor: brand.darker },
          },
          outlined: { borderColor: neutral[300] },
        },
      },

      MuiIconButton: {
        styleOverrides: {
          root: { '@media (pointer: coarse)': { minWidth: COARSE_POINTER_TARGET, minHeight: COARSE_POINTER_TARGET } },
        },
      },

      MuiTextField: { defaultProps: { variant: 'outlined' } },

      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            // Token spec § inputs: 48px tall, 12px radius.
            borderRadius: 12,
            backgroundColor: isDark ? 'transparent' : neutral[0],
            '& .MuiOutlinedInput-notchedOutline': { borderColor: neutral[300] },
            '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: neutral[400] },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderWidth: 2, borderColor: brand.main },
          },
          input: { height: 48, paddingBlock: 0, boxSizing: 'border-box' },
          multiline: { paddingBlock: 12 },
        },
      },

      // A Select renders its value in a `div.MuiSelect-select`, not an `input`,
      // and MUI's own rules for that slot beat the `height: 48` set on
      // `MuiOutlinedInput.input` above. Combined with `paddingBlock: 0`, that
      // left every select collapsed to its line-height (~23px) — a control
      // visibly shorter than the text fields beside it, with no box.
      // Restated here so a select matches the 48px input box by construction.
      MuiSelect: {
        styleOverrides: {
          select: {
            height: 48,
            minHeight: 48,
            boxSizing: 'border-box',
            // The box is a fixed height with no vertical padding, so the value
            // has to be centred rather than sitting on the top edge.
            display: 'flex',
            alignItems: 'center',
          },
        },
      },

      MuiInputLabel: { styleOverrides: { root: { fontSize: '0.95rem' } } },

      MuiCard: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: {
            borderRadius: 16,
            backgroundImage: 'none',
            boxShadow: elevation.sm,
            // Cards had a shadow but no border, which barely separated them
            // from the near-white page background (Pass 1, 2026-07-26).
            // UI Pass 3 (Option 2): the page ground is now blue-tinted, so the
            // card edge is tinted to match rather than the neutral hairline.
            border: `1px solid ${blueTint.wellBorder}`,
            // Token spec § cards: hover raises the shadow. border-color and
            // transform are wired in too, for `cardInteractive` below (not
            // consumed until Pass 2 touches an actual card component).
            transition: `box-shadow ${motion.normal}ms ${motion.easing}, border-color ${motion.normal}ms ${motion.easing}, transform ${motion.normal}ms ${motion.easing}`,
          },
        },
        // `variant="outlined"` today strips the shadow (Paper's own outlined
        // variant never sets one) and draws a border in `divider` grey
        // instead of our card border colour. This `variants` entry -- which
        // MUI applies with higher precedence than `styleOverrides` for
        // exactly this reason -- converges the ten existing
        // `variant="outlined"` call sites onto the same look as every other
        // card, with zero changes at those call sites.
        variants: [
          {
            props: { variant: 'outlined' },
            style: {
              boxShadow: elevation.sm,
              borderColor: blueTint.wellBorder,
              border: undefined,
            },
          },
        ],
      },

      MuiCardContent: { styleOverrides: { root: { padding: 24, '&:last-child': { paddingBottom: 24 } } } },

      MuiPaper: { styleOverrides: { rounded: { borderRadius: 12 } } },

      MuiAppBar: {
        defaultProps: { color: 'inherit', elevation: 0 },
        styleOverrides: {
          root: {
            backgroundColor: isDark ? alpha(neutral[900], 0.85) : alpha(neutral[0], 0.85),
            backdropFilter: 'saturate(180%) blur(8px)',
            color: isDark ? neutral[25] : neutral[900],
            // UI Pass 3 (Option 2): light-mode edge tinted to match the new
            // blue-tinted page ground. Dark mode untouched.
            borderBottom: `1px solid ${isDark ? alpha('#FFFFFF', 0.12) : blueTint.wellBorder}`,
          },
        },
      },

      MuiLink: {
        defaultProps: { underline: 'hover' },
        styleOverrides: { root: { fontWeight: 500, textUnderlineOffset: '2px' } },
      },

      MuiChip: { styleOverrides: { root: { fontWeight: 600, borderRadius: 8 } } },

      MuiTableCell: { styleOverrides: { root: { height: 48, paddingBlock: 0 } } },

      // Pass 1 additions (2026-07-26) below -- dialog/menu/alert/skeleton/
      // stepper defaults that previously fell through to MUI's stock look.

      // MUI's stock dialog radius is 4px; this was flagged as the single
      // cheapest fix in the design audit.
      MuiDialog: { styleOverrides: { paper: { borderRadius: 24 } } },

      MuiAlert: {
        styleOverrides: {
          root: ({ theme, ownerState }) => {
            const key = (ownerState.color ?? ownerState.severity ?? 'info') as
              | 'success'
              | 'info'
              | 'warning'
              | 'error'
            return {
              borderRadius: 12,
              boxShadow: 'none',
              border: `1px solid ${theme.palette[key].light}`,
            }
          },
        },
      },

      MuiMenu: {
        styleOverrides: {
          paper: { borderRadius: 12, boxShadow: elevation.lg, border: `1px solid ${neutral[100]}` },
        },
      },

      MuiPopover: {
        styleOverrides: {
          paper: { borderRadius: 12, boxShadow: elevation.lg, border: `1px solid ${neutral[100]}` },
        },
      },

      MuiSkeleton: { defaultProps: { variant: 'rounded', animation: 'wave' } },

      MuiStepIcon: {
        styleOverrides: {
          root: {
            color: neutral[300],
            '&.Mui-active': { color: brand.main },
            '&.Mui-completed': { color: brand.main },
          },
        },
      },

      MuiStepConnector: {
        styleOverrides: {
          line: { borderColor: neutral[100], borderWidth: 2 },
        },
      },
    },
  })
}

// ---------------------------------------------------------------------------
// Shared sx primitives (Pass 1, 2026-07-26) -- plain `sx` objects, not styled
// components, so later passes can spread them onto whatever element needs
// them without importing a new component.
// ---------------------------------------------------------------------------

/**
 * For interactive (clickable/navigable) cards: a small hover lift plus a
 * border-colour shift, on top of the shadow raise every card already gets.
 * Not consumed yet -- exported for Pass 2, which wires it onto `ListingCard`
 * and similar. See design_system_spec.md §5 "Cards" for the amendment this
 * token exists to satisfy.
 */
export const cardInteractive = {
  transition: `box-shadow ${motion.fast}ms ${motion.easing}, transform ${motion.fast}ms ${motion.easing}, border-color ${motion.fast}ms ${motion.easing}`,
  '&:hover': {
    boxShadow: elevation.md,
    transform: 'translateY(-2px)',
    // UI Pass 3 (Option 2): the browse grid's card-hover border now turns
    // brand blue instead of grey, on top of the color rollout.
    borderColor: brand.light,
  },
  // The lift is motion; the shadow change is not, so only the transform is
  // dropped for users who asked for reduced motion.
  '@media (prefers-reduced-motion: reduce)': {
    '&:hover': { transform: 'none' },
  },
} as const

/** A recessed/inset surface (e.g. a quoted figure, a code/id chip well). */
export const surfaceRecessed = {
  // UI Pass 3 (Option 2): blue-tinted well instead of plain slate, to match
  // the rest of the color rollout. Propagates to every existing consumer
  // (EmptyState.tsx, ListingCard.tsx, ListingDetail.tsx) with no call-site edit.
  backgroundColor: blueTint.well,
  border: `1px solid ${blueTint.wellBorder}`,
  boxShadow: elevation.inset,
  borderRadius: 2, // MUI's sx borderRadius multiplies by theme.shape.borderRadius (8) -> 16px, matching the card radius.
} as const

/** Outlined button on a blue-tinted surface — landing/spotlight-card CTAs only. */
export const outlinedBrandTint = {
  borderColor: blueTint.washBorder,
  color: blueTint.onWash,
  '&:hover': { borderColor: brand.main, backgroundColor: brandTint },
} as const

/** A small KPI/metric pair -- label above value. Pairs with `Metric.tsx`. */
export const metricLabel = {
  fontSize: '0.6875rem',
  fontWeight: 600,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: 'text.secondary',
} as const

export const metricValue = {
  fontSize: '1.0625rem',
  fontWeight: 700,
  letterSpacing: '-0.02em',
  color: 'text.primary',
  ...tabularNums,
} as const

/** The app theme (light). Swap/branch via `createAppTheme('dark')` when ready. */
export const theme = createAppTheme('light')

export default theme
