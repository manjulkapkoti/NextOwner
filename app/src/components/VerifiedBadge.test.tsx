// M10 — VerifiedBadge (spec 010 D7, S11).
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { VerifiedBadge } from './VerifiedBadge'

describe('VerifiedBadge', () => {
  it('renders the Verified chip when verified is true', () => {
    render(<VerifiedBadge verified />)
    expect(screen.getByText('Verified')).toBeInTheDocument()
  })

  // S11's negative twin at the component level: a revoke flips `verified` to
  // false, and the badge must not linger — it renders nothing, not a stale
  // "Verified" label and not some other leftover chip.
  it('renders nothing when verified is false', () => {
    const { container } = render(<VerifiedBadge verified={false} />)
    expect(container).toBeEmptyDOMElement()
  })
})
