# Design System — NextOwner

> The deliberate design foundation, decided **once**, so screens aren't styled by
> accident. Binding for UI work the way `security.md` is for security.
>
> **Context:** NextOwner went to production (memory: production-pivot), so a
> **world-class, professional, responsive** UI is a first-class requirement
> (memory: ui-quality-bar). This retired the app-shell spec's "design system is
> a later concern" deferral.
>
> **Provenance:** this file absorbs the authored *NextOwner Design Tokens v1.0*
> and *Design System v1.0* specs (2026-07-18). They were consolidated here on
> the owner's call — three documents defining the same tokens is the
> "duplicated truth maintained by nobody" failure recorded in the
> constitution's 2026-07-18 amendment. The originals remain in git history.

---

## 0. The one rule about this document

**Two artefacts, one job each — nothing is defined twice:**

| | Holds | Example |
|---|---|---|
| **`app/src/theme.ts`** | **Every literal value.** The single source of token truth. | `primary.main`, the neutral ramp, shadows, badge pairs |
| **This file** | **Every decision and its reason.** What we chose, what we rejected, and why. | *why* the CTA is blue, *why* the focus ring was changed |

If a hex appears below, it is because the *reasoning* is the point (a rejected value, a measured failure) — not because this file is a second palette. **For "what colour is X", read `theme.ts`.**

## 1. What this product *is*, in design terms

NextOwner is a **trust-and-money marketplace** — people list businesses worth six and seven figures and hand confidential financials to strangers. The design job is **credibility first**: it must look like somewhere you'd trust a life-changing transaction, the way Stripe/Mercury/Ramp look like somewhere you'd trust your money.

**References, used deliberately:**
- **Aesthetic bar → world-class SaaS/fintech** (Stripe, Linear, Mercury, Ramp): restraint, generous whitespace, crisp type, confident but calm colour, subtle depth. The M&A category itself (Flippa etc.) skews dated and busy — we take its *trust patterns*, not its look.
- **Trust-UX mechanics → the category** (Empire Flippers, Baton, Acquire): how gated data is teased, how "verified" is signalled, how a listing's state is shown. These are the product-specific patterns generic SaaS won't hand us.

Positioning in one line: **premium, trustworthy, minimal — built for buying and selling businesses, not consumer ecommerce.**

## 2. Principles

1. **Calm, not loud.** One confident primary colour, used sparingly for action. Colour earns attention; most of the screen is neutral. Money products don't shout. Target mix: **~70% neutral, ~20% blue, ~10% accent.**
2. **Whitespace is structure.** Generous spacing and clear hierarchy over borders and boxes.
3. **Every state is designed.** Empty, loading, error, and — uniquely here — *gated/locked* are first-class. They're where trust products feel broken or feel solid.
4. **Responsive by default.** Everything works thumb-first on a phone and scales up. No fixed-width desktop-only layouts.
5. **Legible before decorative.** A real type scale, AA contrast, nothing that fights the readability of financial figures.
6. **One primary CTA per screen.** If two things are primary, neither is.
7. **Icons support text, never replace it.** An icon-only control needs an accessible name and, usually, a label.
8. **Confirm irreversible actions.** Deleting a listing, revoking access, accepting an offer.

## 3. The decisions (values live in `theme.ts`)

- **Type:** **Manrope** for display headings (h1–h4), **Inter** for UI and body — both self-hosted via `@fontsource`, so there is no external font request (CSP-safe, works offline). Tabular numerals are opt-in (`tabularNums`) for money and metrics so columns align; prose keeps proportional figures.
- **Colour — primary is blue.** Used only for primary actions, links, and focus. **Orange is a brand accent, not an action colour** — see §4.
- **Colour — neutrals** are a cool-grey (slate) ramp at AA contrast, not MUI's flat default greys.
- **Shape:** 8px base radius; cards 16px; inputs 12px. Rounded and professional, not bubbly. Cards use a soft low shadow rather than a hard border.
- **Elevation:** three shadows only (sm/md/lg), slate-tinted rather than pure black. **Depth signals interactivity; it is not decoration.** Card hover raises the shadow and changes nothing else.
- **Spacing:** a 4px grid. See §4 for how it maps onto MUI's multiplier.
- **Motion:** 150ms hover · 250ms transitions · 350ms dialogs, on `cubic-bezier(0.4, 0, 0.2, 1)`. Wired into `theme.transitions` so components inherit it rather than hand-rolling durations.
- **Breakpoints:** 0 / 768 / 1024 / 1280 / 1536. `sm` (768) is the tablet boundary where the nav collapses to a menu.
- **Layout floor: 360px.** Below it the viewport scrolls horizontally instead of the layout wrapping — a scrollbar is a better failure than broken chrome. 360px is the narrowest mainstream phone, so it should never be hit in practice.

## 4. Deviations from the authored v1 spec (deliberate, measured)

The v1 spec requires **"WCAG AA contrast"**, and several of its literal colour values fail that requirement. Contrast was measured, not estimated; **the requirement was kept and the values adjusted.**

| Spec value | Measured on white | Implemented instead | Why |
|---|---|---|---|
| focus ring `#93C5FD` | **1.80:1** | brand blue (5.17:1) | WCAG 2.2 requires **3:1** for a focus indicator; the spec's ring is nearly invisible on white |
| success `#10B981` | 2.54:1 | `#15803D` (5.02:1) | fails as text or as a filled button |
| warning `#F59E0B` | 2.15:1 | `#B45309` (5.02:1) | as above |
| info `#0EA5E9` | 2.77:1 | `#0369A1` (5.93:1) | as above; also sat too close to primary blue |
| accent `#F97316` | 2.80:1 | kept as a **fill**; `#C2410C` for text | cannot carry white text |

The spec's brighter hues are **not discarded** — they survive as the *light fills* in the `badge` tokens, where dark text sits on them (every pair ≥5.3:1). That pairing is what makes them usable.

**Three further resolutions:**

- **CTA colour — blue, not orange.** The spec contradicts itself: its principles say *"Orange = emphasis & CTAs"*, its component rules say *"Buttons — Primary: blue fill"*. Blue wins on the contrast evidence above. Orange is reserved for the logo and the Featured badge, which also stops it colliding with `warning` amber — a brand accent that reads as "something needs attention" is worse than no accent.
- **Spacing — the 4px grid on MUI's 8px multiplier.** A deviation in mechanism, not outcome: every value on the spec's scale is reachable and lands on a 4px multiple (4 = `0.5`, 12 = `1.5`, 20 = `2.5`). Setting the multiplier to 4 would have silently halved every spacing value already written across six screens, for no visual gain.
- **44px touch targets on coarse pointers only** (`@media (pointer: coarse)`). The guideline exists for fingers; applying a 44px floor to every small desktop button would bloat the UI it was meant to help.

**Not yet implemented:** JetBrains Mono (nothing renders code yet), listing-card / table / chart rules (M4+), and dark mode — the palette values exist but no screen exercises them.

## 5. Component rules

- **Buttons.** Primary: blue fill, white text. Secondary: white with a grey border. Ghost: transparent. Destructive: red. No ALL-CAPS. Primary gets a small shadow that lifts on hover; nothing else does.
- **Inputs.** One height across the app (48px), 12px radius, focus ring in brand blue at 2px. Validation is the server's: the form submits and renders the 422 inline rather than blocking with native popups.
- **Cards.** White surface, 16px radius, 24px padding, soft shadow. **Hover raises the shadow only** — no transform, no border change.
- **Navigation.** White top bar, sticky. Auth actions top-right at every width. Below `sm` the authed actions collapse behind one menu control. Active item in blue.
- **Badges.** Verified = green · Featured = orange · Premium = purple · Sold = grey. Always a light fill with dark text, **never colour alone** — every badge carries a label.
- **Tables.** Sticky header, 48px rows, hover-only row highlight (no zebra striping). Prefer cards over tables on mobile.
- **Charts** (M11+). Revenue blue · Growth green · Costs orange · Loss red.

## 6. The trust vocabulary (decided now, wired as milestones arrive)

The product-specific core — a seller or admin reads these constantly:

- **Listing status:** `draft` → neutral · `pending_review` → amber · `live` → green · `paused` → muted slate · `under_offer` → blue · `sold` → closed treatment · `rejected` → red. These map to **`StatusChip`** so the status language is identical everywhere. **Built** — it was scheduled for M3, but the dashboard renders statuses today, so building it here means M3 and M4 inherit it rather than re-inventing chip colours. Unknown statuses degrade to a plain chip rather than crashing, so a new backend status is safe.
- **Gated / locked data** (the NDA gate, M5): a consistent "blurred value + lock affordance + what unlocks it" treatment. The tokens are set now; the component lands with M5.
- **Verified badges** (buyer/seller, M10): one treatment, reused.
- **Anonymous public card vs. unlocked private view** (M4/M5): the public card deliberately *shows the shape of the deal* (metrics, ranges) while hiding identity — the tease, not a blank.

## 7. Voice — shipped in M4

The positioning is **succession, not transaction**: a business existed before the sale and continues after it, and the seller **chooses who carries it forward**. That's a description of `access_request` (`requested → approved|denied`), not a slogan — the brand promise and the architecture are the same sentence, which is why we can claim it and a public-listing competitor can't.

**Shipped in M4** (spec `004-marketplace-browse` criterion F7; deferred here by the owner 2026-07-18 and landed when the public browse and the buyer-side story existed to carry it).

**Binding on every surface:** the story lives in **headlines and prose only**. **Navigation and control labels stay literal** — "Browse", "My listings", "Create account", "Log in". A label a user has to decode trades usability for poetry, which inverts this product's stated UI bar (§2). Write the hero with voice; write the buttons plain.

### The two audiences

The **seller is the lead audience** — supply is the scarce side of a marketplace, and the succession story is theirs. But a seller-led framing gives a buyer no reason to be here, so **the buyer counter-story gets equal billing**, never a footnote: *take over something real — with customers, revenue and a history — instead of starting from zero.*

### Words to use, words to avoid

| Use | Avoid | Why |
|---|---|---|
| next owner, carries it forward, succession | buy and sell, exit, flip | "Buy and sell" frames a business as inventory — the framing every competitor uses |
| you decide who gets to look | listing visibility, lead gen | the NDA gate is a seller's *choice*, not a settings toggle |
| take over something real | acquire an asset | buyers are operators, not portfolio managers |
| locked until the NDA is signed | premium, upgrade | the gate is about trust, not tiering (it is also the future paywall surface — don't pre-empt that) |

### Inheritance

Surfaces built after M4 inherit this section rather than reinventing a tone — in particular **M8's notification emails and saved-search alerts**, which are the next place prose reaches a user unprompted. An email that says "a new business is for sale" has silently reverted to the competitor framing; "a business is looking for its next owner" has not.

## 8. Accessibility (non-negotiable)

- **WCAG AA contrast**, verified by measurement — see §4 for what that changed.
- **Visible keyboard focus** on every interactive element; the ring is explicit, not the browser default.
- **Never colour alone.** Status and badges always carry text.
- **44px minimum touch target** on touch devices.
- Icon-only controls carry an accessible name; composite marks (the logo lockup) expose **one** name, not their parts.

## 9. Scope

- **Done:** `theme.ts` implementing the tokens, self-hosted fonts via `ThemeProvider`, `StatusChip`, and **all six screens** restyled — landing, login, signup, nav, seller dashboard, listing wizard.
- **Next:** every M3+ screen is built to this bar, using `StatusChip` wherever a listing status renders.
- **Deferred (with the production phase):** a component library / Storybook, an animation system, dark mode (the palette is ready, no screen uses it), and illustration.
