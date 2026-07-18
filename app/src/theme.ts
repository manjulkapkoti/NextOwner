// NextOwner MUI theme — the design tokens from docs/design_system.md made real.
//
// This is the single source of visual truth (the doc is the *why*, this is the
// *what*). Credibility-first: calm confident indigo used sparingly, cool-grey
// neutrals at AA contrast, an 8px-based radius/spacing system, soft low
// shadows, and Inter (self-hosted). Structured as `getDesignTokens(mode)` so a
// dark palette can be added later by filling in the `dark` branch — no rewrite.
import { createTheme, alpha } from '@mui/material/styles'
import type { PaletteMode, Shadows, ThemeOptions } from '@mui/material/styles'

// ---------------------------------------------------------------------------
// Raw tokens
// ---------------------------------------------------------------------------

/** Cool-grey (slate) neutral ramp — replaces MUI's flat default greys. */
export const neutral = {
  50: '#F8FAFC',
  100: '#F1F5F9',
  200: '#E2E8F0',
  300: '#CBD5E1',
  400: '#94A3B8',
  500: '#64748B',
  600: '#475569',
  700: '#334155',
  800: '#1E293B',
  900: '#0F172A',
} as const

/** Deep, confident indigo — the one action/brand colour. Used sparingly. */
export const brand = {
  main: '#4338CA', // indigo-700 — primary actions, links, focus
  dark: '#3730A3', // hover / active (darker)
  light: '#6366F1', // lighter accent
  contrastText: '#FFFFFF',
} as const

/** Pale indigo wash for selected / hover *surfaces* (not fills of the brand). */
export const brandTint = '#EEF2FF'

/**
 * Opt-in tabular figures so money/metrics columns align. Spread into `sx` on
 * any element that renders currency or KPIs, e.g. `sx={{ ...tabularNums }}`.
 * (Kept opt-in: Inter's proportional figures read better in prose.)
 */
export const tabularNums = { fontVariantNumeric: 'tabular-nums' } as const

// ---------------------------------------------------------------------------
// Soft, restrained elevation set (depth signals interactivity, not decoration)
// ---------------------------------------------------------------------------

const shadowRGB = '15, 23, 42' // slate-900, for tinted (not pure-black) shadows
const softShadows = [...createTheme().shadows] as Shadows
softShadows[1] = `0 1px 2px 0 rgba(${shadowRGB}, 0.04), 0 1px 3px 0 rgba(${shadowRGB}, 0.06)`
softShadows[2] = `0 1px 3px 0 rgba(${shadowRGB}, 0.05), 0 2px 8px -2px rgba(${shadowRGB}, 0.08)`
softShadows[3] = `0 2px 6px -1px rgba(${shadowRGB}, 0.06), 0 6px 16px -4px rgba(${shadowRGB}, 0.10)`
softShadows[4] = `0 4px 10px -2px rgba(${shadowRGB}, 0.08), 0 10px 24px -6px rgba(${shadowRGB}, 0.12)`
softShadows[6] = `0 6px 14px -3px rgba(${shadowRGB}, 0.10), 0 14px 32px -8px rgba(${shadowRGB}, 0.14)`
softShadows[8] = `0 8px 18px -4px rgba(${shadowRGB}, 0.12), 0 20px 40px -10px rgba(${shadowRGB}, 0.16)`

// ---------------------------------------------------------------------------
// Palette — keyed by mode so dark mode is a fill-in, not a rewrite
// ---------------------------------------------------------------------------

function getPalette(mode: PaletteMode): ThemeOptions['palette'] {
  // The listing-status vocabulary (design_system.md §3) rides on the semantic
  // colours below: draft→neutral, pending_review→warning, live→success,
  // under_offer→info, rejected→error. StatusChip (a later milestone) reads them.
  const semantic = {
    primary: { ...brand },
    success: { main: '#16A34A', light: '#DCFCE7', dark: '#15803D', contrastText: '#FFFFFF' },
    warning: { main: '#D97706', light: '#FEF3C7', dark: '#B45309', contrastText: '#FFFFFF' },
    error: { main: '#DC2626', light: '#FEE2E2', dark: '#B91C1C', contrastText: '#FFFFFF' },
    info: { main: '#2563EB', light: '#DBEAFE', dark: '#1D4ED8', contrastText: '#FFFFFF' },
    grey: neutral,
  }

  if (mode === 'dark') {
    // Deferred (docs/design_system.md §5) — sensible defaults so the structure
    // exists and can be tuned when dark mode ships.
    return {
      mode,
      ...semantic,
      background: { default: neutral[900], paper: neutral[800] },
      text: { primary: '#F8FAFC', secondary: neutral[300], disabled: neutral[500] },
      divider: alpha('#FFFFFF', 0.12),
    }
  }

  return {
    mode,
    ...semantic,
    background: { default: neutral[50], paper: '#FFFFFF' },
    text: { primary: neutral[900], secondary: neutral[600], disabled: neutral[400] },
    divider: neutral[200],
  }
}

// ---------------------------------------------------------------------------
// Theme factory
// ---------------------------------------------------------------------------

export function createAppTheme(mode: PaletteMode = 'light') {
  const palette = getPalette(mode)

  return createTheme({
    palette,
    shape: { borderRadius: 8 },
    shadows: softShadows,

    typography: {
      fontFamily:
        '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
      // Tightened tracking on headings reads as "designed", not default.
      h1: { fontSize: '3rem', fontWeight: 700, lineHeight: 1.1, letterSpacing: '-0.022em' },
      h2: { fontSize: '2.25rem', fontWeight: 700, lineHeight: 1.15, letterSpacing: '-0.02em' },
      h3: { fontSize: '1.875rem', fontWeight: 700, lineHeight: 1.2, letterSpacing: '-0.018em' },
      h4: { fontSize: '1.5rem', fontWeight: 600, lineHeight: 1.25, letterSpacing: '-0.015em' },
      h5: { fontSize: '1.25rem', fontWeight: 600, lineHeight: 1.3, letterSpacing: '-0.01em' },
      h6: { fontSize: '1.125rem', fontWeight: 600, lineHeight: 1.4, letterSpacing: '-0.006em' },
      subtitle1: { fontSize: '1rem', fontWeight: 500, lineHeight: 1.5 },
      subtitle2: { fontSize: '0.875rem', fontWeight: 600, lineHeight: 1.5 },
      body1: { fontSize: '1rem', lineHeight: 1.6, letterSpacing: '-0.002em' },
      body2: { fontSize: '0.875rem', lineHeight: 1.55, letterSpacing: '-0.001em' },
      button: { fontWeight: 600, letterSpacing: 0, textTransform: 'none' },
      caption: { fontSize: '0.75rem', lineHeight: 1.4, letterSpacing: '0.01em' },
      overline: { fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase' },
    },

    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            WebkitFontSmoothing: 'antialiased',
            MozOsxFontSmoothing: 'grayscale',
            textRendering: 'optimizeLegibility',
          },
          '::selection': { backgroundColor: alpha(brand.main, 0.16) },
        },
      },

      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: {
            borderRadius: 8,
            paddingInline: 18,
            paddingBlock: 8,
            transition: 'background-color 120ms ease, box-shadow 120ms ease, border-color 120ms ease',
          },
          sizeLarge: { paddingInline: 24, paddingBlock: 11, fontSize: '1rem' },
          sizeSmall: { paddingInline: 12, paddingBlock: 5 },
          // The one loud element — give the primary CTA a touch of lift.
          containedPrimary: {
            boxShadow: `0 1px 2px 0 rgba(${shadowRGB}, 0.10)`,
            '&:hover': { boxShadow: `0 4px 12px -2px ${alpha(brand.main, 0.35)}` },
          },
          outlined: { borderColor: neutral[300] },
        },
      },

      MuiTextField: { defaultProps: { variant: 'outlined' } },

      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            backgroundColor: '#FFFFFF',
            '& .MuiOutlinedInput-notchedOutline': { borderColor: neutral[300] },
            '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: neutral[400] },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderWidth: 1.5 },
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
            boxShadow: softShadows[3],
          },
        },
      },

      MuiPaper: { styleOverrides: { rounded: { borderRadius: 12 } } },

      MuiAppBar: {
        defaultProps: { color: 'inherit', elevation: 0 },
        styleOverrides: {
          root: {
            backgroundColor: alpha('#FFFFFF', 0.85),
            backdropFilter: 'saturate(180%) blur(8px)',
            color: neutral[900],
            borderBottom: `1px solid ${neutral[200]}`,
          },
        },
      },

      MuiLink: {
        defaultProps: { underline: 'hover' },
        styleOverrides: { root: { fontWeight: 500, textUnderlineOffset: '2px' } },
      },

      MuiChip: { styleOverrides: { root: { fontWeight: 600, borderRadius: 8 } } },
    },
  })
}

/** The app theme (light). Swap/branch via `createAppTheme('dark')` when ready. */
export const theme = createAppTheme('light')

export default theme
