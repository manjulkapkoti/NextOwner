# NextOwner Design Tokens v1.0

## Principles
- Premium SaaS marketplace
- Neutral-first UI
- Blue = trust & primary actions
- Orange = emphasis & CTAs
- Green = success only

```yaml
meta:
  name: NextOwner
  version: 1.0.0

color:
  brand:
    primary: "#2563EB"
    primary_hover: "#1D4ED8"
    primary_active: "#1E40AF"
    secondary: "#F97316"
    secondary_hover: "#EA580C"
    secondary_active: "#C2410C"

  background:
    canvas: "#F8FAFC"
    surface: "#FFFFFF"
    surface_alt: "#F1F5F9"
    inverse: "#020617"

  text:
    primary: "#0F172A"
    secondary: "#475569"
    tertiary: "#64748B"
    disabled: "#94A3B8"
    inverse: "#FFFFFF"

  border:
    subtle: "#F1F5F9"
    default: "#E2E8F0"
    strong: "#CBD5E1"
    focus: "#93C5FD"

  state:
    success: "#10B981"
    warning: "#F59E0B"
    error: "#DC2626"
    info: "#0EA5E9"

  badge:
    verified_bg: "#DCFCE7"
    verified_fg: "#15803D"
    featured_bg: "#FFEDD5"
    featured_fg: "#EA580C"
    premium_bg: "#EDE9FE"
    premium_fg: "#7C3AED"

typography:
  family:
    primary: "Inter"
    display: "Manrope"
    mono: "JetBrains Mono"
  weight:
    regular: 400
    medium: 500
    semibold: 600
    bold: 700
  size:
    xs: 12
    sm: 14
    md: 16
    lg: 18
    xl: 20
    "2xl": 24
    "3xl": 30
    "4xl": 36

spacing:
  unit: 4
  scale: [0,4,8,12,16,20,24,32,40,48,64,80,96]

radius:
  xs: 4
  sm: 8
  md: 12
  lg: 16
  xl: 24
  full: 9999

shadow:
  sm: "0 1px 2px rgba(15,23,42,0.05)"
  md: "0 4px 12px rgba(15,23,42,0.08)"
  lg: "0 12px 24px rgba(15,23,42,0.12)"

motion:
  fast: 150ms
  normal: 250ms
  slow: 350ms
  easing: "cubic-bezier(0.4,0,0.2,1)"

layout:
  container:
    max_width: 1280
  grid:
    columns: 12
    gutter: 24

usage:
  color_ratio:
    neutral: "70%"
    blue: "20%"
    orange: "10%"
```
