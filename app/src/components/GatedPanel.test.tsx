// UI Pass 3 (trust-gate consolidation) — the shared "gated" visual treatment
// used by `ListingCard`, `ListingDetail`, and `RequestAccessPanel`.
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { GatedPanel } from './GatedPanel'

describe('GatedPanel', () => {
  it.each(['locked', 'pending', 'denied'] as const)(
    'renders its lock icon and children for variant=%s',
    (variant) => {
      render(
        <GatedPanel variant={variant}>
          <p>child content for {variant}</p>
        </GatedPanel>,
      )
      expect(screen.getByText(`child content for ${variant}`)).toBeInTheDocument()
      // The lock icon is `LockOutlinedIcon` from @mui/icons-material, which
      // renders an <svg data-testid="LockOutlinedIcon">.
      expect(screen.getByTestId('LockOutlinedIcon')).toBeInTheDocument()
    },
  )

  it('renders each redacted field as visible, accessible text with a decorative placeholder', () => {
    const fields = ['Company name', 'Website', 'Detailed financials']
    const { container } = render(
      <GatedPanel variant="locked" redactedFields={fields}>
        <p>teaser copy</p>
      </GatedPanel>,
    )

    for (const field of fields) {
      // Real, accessible text — not decorative.
      expect(screen.getByText(field)).toBeInTheDocument()
    }

    // One decorative, aria-hidden placeholder bar per field. Scoped to `div`
    // so the (also aria-hidden) lock icon `<svg>` doesn't inflate the count.
    const hiddenPlaceholders = container.querySelectorAll('div[aria-hidden="true"]')
    expect(hiddenPlaceholders.length).toBe(fields.length)

    // The redaction invariant itself, not just the label/bar count (found by
    // an independent appsec pass via sabotage: inserting text as a child of
    // the aria-hidden bar left every other assertion here green). A future
    // caller deriving `redactedFields` from real listing data, or a future
    // edit rendering a value inside the bar, must fail here.
    hiddenPlaceholders.forEach((bar) => {
      expect(bar.textContent).toBe('')
    })
  })

  it('renders no redacted rows when redactedFields is omitted', () => {
    const { container } = render(
      <GatedPanel variant="pending">
        <p>pending copy</p>
      </GatedPanel>,
    )
    expect(container.querySelectorAll('div[aria-hidden="true"]').length).toBe(0)
  })

  it('renders no redacted rows when redactedFields is an empty array', () => {
    const { container } = render(
      <GatedPanel variant="denied" redactedFields={[]}>
        <p>denied copy</p>
      </GatedPanel>,
    )
    expect(container.querySelectorAll('div[aria-hidden="true"]').length).toBe(0)
  })

  it('renders exactly one icon for both size variants', () => {
    const { container: fullContainer } = render(
      <GatedPanel variant="locked">
        <p>full</p>
      </GatedPanel>,
    )
    const { container: compactContainer } = render(
      <GatedPanel variant="locked" size="compact">
        <p>compact</p>
      </GatedPanel>,
    )
    expect(fullContainer.querySelectorAll('[data-testid="LockOutlinedIcon"]').length).toBe(1)
    expect(compactContainer.querySelectorAll('[data-testid="LockOutlinedIcon"]').length).toBe(1)
  })
})
