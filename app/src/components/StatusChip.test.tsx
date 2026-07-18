// The listing status vocabulary (docs/design_system_spec.md §6).
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusChip } from './StatusChip'

describe('StatusChip', () => {
  it('renders a human label for each status in the state machine', () => {
    const cases: Array<[string, RegExp]> = [
      ['draft', /^Draft$/],
      ['pending_review', /^In review$/],
      ['live', /^Live$/],
      ['paused', /^Paused$/],
      ['under_offer', /^Under offer$/],
      ['sold', /^Sold$/],
      ['rejected', /^Rejected$/],
    ]
    for (const [status, label] of cases) {
      const { unmount } = render(<StatusChip status={status} />)
      expect(screen.getByText(label)).toBeInTheDocument()
      unmount()
    }
  })

  // The colour is reinforcement, never the message (design_system_spec.md §8 —
  // "never colour alone"), so the label must always be readable text.
  it('always carries a text label, not colour alone', () => {
    render(<StatusChip status="live" />)
    expect(screen.getByText('Live')).toBeInTheDocument()
  })

  // A status the frontend does not know about must degrade to a plain chip
  // rather than crash the dashboard — the backend can add one at any time.
  it('falls back to the raw value for an unknown status', () => {
    render(<StatusChip status="archived_by_admin" />)
    expect(screen.getByText('archived_by_admin')).toBeInTheDocument()
  })
})
