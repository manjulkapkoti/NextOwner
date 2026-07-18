# Design System — NextOwner

> The deliberate design foundation, decided **once**, so screens aren't styled by
> accident. Binding for UI work the way `security.md` is for security. Tokens
> live in `app/src/theme.ts` (the MUI theme); this doc is the *why*.
>
> **Context:** NextOwner went to production (memory: production-pivot), so a
> **world-class, professional, responsive** UI is a first-class requirement
> (memory: ui-quality-bar). This retires the app-shell spec's "design system is
> a later concern" deferral.

---

## 0. Which document is which (read this first)

Three files describe the design, and only one of them is live:

| File | Role |
|---|---|
| **`app/src/theme.ts`** | **The implementation, and the single source of token truth.** If a value is disputed, this file wins. |
| **`docs/design_system.md`** (this file) | The *why* — principles, product-specific vocabulary, and the record of deliberate deviations. |
| `docs/design_tokens_v1.md`, `docs/design_system_v1_spec.md` | **The authored v1 spec — an input, kept as written.** Historical: it is what was asked for, not a live description of what exists. Where it and `theme.ts` disagree, see § Deviations. |

*Why this hierarchy exists:* three documents each claiming to define the same tokens is the "duplicated truth maintained by nobody" failure recorded in the constitution's 2026-07-18 amendment — the one that let the project status rot for two milestones. One home per fact, and the spec files are explicitly **not** that home.

## 0b. Deviations from the v1 spec (deliberate, measured)

The v1 spec requires **"WCAG AA contrast"**, and several of its literal colour values fail that requirement. Contrast was measured, not estimated; the requirement was kept and the values adjusted.

| Spec value | Measured on white | Implemented instead | Why |
|---|---|---|---|
| focus ring `#93C5FD` | **1.80:1** | `#2563EB` (5.17:1) | WCAG 2.2 requires **3:1** for a focus indicator; the spec's ring is nearly invisible on white |
| success `#10B981` | 2.54:1 | `#15803D` (5.02:1) | fails as text or as a filled button |
| warning `#F59E0B` | 2.15:1 | `#B45309` (5.02:1) | as above |
| info `#0EA5E9` | 2.77:1 | `#0369A1` (5.93:1) | as above; also sat too close to primary blue |
| accent `#F97316` | 2.80:1 | kept as a **fill**; `#C2410C` for text | cannot carry white text |

The spec's brighter hues are not discarded — they survive as the **light fills** in the `badge` tokens, where dark text sits on them (every pair measures ≥5.3:1). That is the pairing that makes them usable.

**Two further resolutions:**

- **CTA colour — blue, not orange.** The spec contradicts itself: its principles say *"Orange = emphasis & CTAs"*, its component rules say *"Buttons — Primary: blue fill"*. Blue wins on the contrast evidence above. Orange is reserved for the logo and the Featured badge, which also keeps it from colliding with `warning` amber — a brand accent that reads as "something needs attention" is worse than no accent.
- **Spacing — the 4px grid on MUI's 8px multiplier.** A deviation in mechanism, not outcome: every value on the spec's scale is reachable and lands on a 4px multiple (4 = `0.5`, 12 = `1.5`, 20 = `2.5`). Setting the multiplier to 4 would have silently halved every spacing value already written across six screens, for no visual gain.

**Not yet implemented from the spec:** JetBrains Mono (nothing renders code yet), listing-card/table/chart rules (M4+), and dark mode (values are in the palette but no screen exercises them).

---

## 1. What this product *is*, in design terms

NextOwner is a **trust-and-money marketplace** — people list businesses worth six and seven figures and hand over confidential financials to strangers. The design job is therefore **credibility first**: it must look like somewhere you'd trust a life-changing transaction, the way Stripe/Mercury/Ramp look like somewhere you'd trust your money.

**References, used deliberately:**
- **Aesthetic bar → world-class SaaS/fintech** (Stripe, Linear, Mercury, Ramp): restraint, generous whitespace, crisp type, confident but calm color, subtle depth. The M&A category itself (Flippa etc.) skews dated and busy — we take its *trust patterns*, not its look.
- **Trust-UX mechanics → the category** (Empire Flippers, Baton, Acquire): how gated data is teased, how "verified" is signaled, how a listing's state is shown. These are the genuinely product-specific patterns generic SaaS won't hand us.

## 2. Principles

1. **Calm, not loud.** One confident primary color, used sparingly for action. Color earns attention; most of the screen is neutral. Money products don't shout.
2. **Whitespace is structure.** Generous spacing and clear hierarchy over borders and boxes. Let content breathe.
3. **Every state is designed.** Empty, loading, error, and — uniquely here — *gated/locked* are first-class, not afterthoughts (they're where trust products feel broken or feel solid).
4. **Responsive by default.** Mobile-first: everything works thumb-first on a phone and scales up. No fixed-width desktop-only layouts.
5. **Legible before decorative.** A real type scale, strong contrast (WCAG AA), no styling that fights readability of financial figures.

## 3. Tokens (the decisions — implemented in `theme.ts`)

- **Type:** **Manrope** for display headings (h1–h4), **Inter** for UI and body — both self-hosted (`@fontsource`), so no external font request (CSP-safe, offline-capable). The v1 spec's size/line-height ramp, with tightened heading letter-spacing. Tabular numerals for money/metrics so columns align.
- **Color — primary:** **brand blue `#2563EB`** (5.17:1 on white), used only for primary actions, links, and focus. Hover `#1D4ED8`, active `#1E40AF`; a light tint for selected/hover surfaces. **Orange is not an action colour** — see § Deviations.
- **Color — neutrals:** a proper cool-grey scale (background, surface, borders, three text weights) with AA contrast — not MUI's flat default greys.
- **Touch targets:** a 44px minimum on coarse pointers only (`@media (pointer: coarse)`), so phones get the accessible target without desktop controls turning chunky.
- **Color — semantic + the listing status vocabulary** (this is the product-specific core; a seller/admin reads these constantly):
  - `draft` → neutral grey · `pending_review` → amber (warning) · `live` → green (success) · `paused` → muted slate · `under_offer` → blue (info) · `sold` → solid "closed" treatment · `rejected` → red (error).
  - These map to a `StatusChip` component so the status language is identical everywhere.
- **Shape:** 8px base radius (buttons/inputs/cards) — rounded, professional, not bubbly. Cards get a soft, low shadow, not a hard border.
- **Elevation:** restrained — a small set of soft shadows; depth signals interactivity, it isn't decoration.
- **Spacing:** the spec's 4px grid, expressed on MUI's 8px multiplier (§ Deviations); layouts use it consistently, no magic pixel values.
- **Motion:** 150ms hover / 250ms transitions / 350ms dialogs on `cubic-bezier(0.4, 0, 0.2, 1)`, wired into the theme's `transitions` so components inherit it.

## 4. The trust vocabulary (decided now, some wired later)

Decided here so it's coherent when the milestones that need it arrive:
- **Gated / locked data** (the NDA gate, M5): a consistent "blurred value + lock affordance + what-unlocks-it" treatment. The *token* (a lock color + blur style) is set now; the component lands with M5.
- **Verified badges** (buyer/seller, M10): one badge treatment, reused.
- **Anonymous public card vs. unlocked private view** (M4/M5): the public card deliberately *shows the shape of the deal* (metrics, ranges) while hiding identity — the tease, not a blank.

## 4b. Voice — deferred to M4 (recorded so it isn't re-litigated)

The positioning is **succession, not transaction**: a business existed before the sale and continues after it, and the seller **chooses who carries it forward**. That is a description of `access_request` (`requested → approved|denied`), not a slogan — the brand promise and the architecture are the same sentence, which is why we can claim it and a public-listing competitor can't.

**The copy lands in M4** (owner's call, 2026-07-18), when the public browse surfaces and the buyer-side story exist to carry it; today's landing hero is a stopgap. Full scope in `milestones.md` § Scope fold-ins → M4.

**Binding on every surface, starting now:** the story lives in **headlines and prose only**. **Navigation and control labels stay literal** — "My listings", "Create account", "Log in". A label a user has to decode trades usability for poetry, which inverts this product's stated UI bar (§2). Write the hero with voice; write the buttons plain.

## 5. Scope of the current pass

- **Now:** `theme.ts` + `@fontsource/inter`, wired via `ThemeProvider`; restyle the **6 existing screens** (landing, login, register, dashboard, listing wizard, nav) to this system; verify responsive + all tests green.
- **Applied going forward:** every M3+ screen is built to this bar; `StatusChip` is used the moment listing statuses render (M3 curation, M4 browse).
- **Deferred (with the production phase):** a full component library / Storybook, motion/animation system, dark mode (the theme is structured so it can be added), and brand identity (logo, illustration) — not blocking, and cheaper once the product is fuller.
