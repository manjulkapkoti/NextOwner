// UI Pass 1 shared primitive (docs/design_system_spec.md).
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Metric } from './Metric'

describe('Metric', () => {
  it('renders the label and value', () => {
    render(<Metric label="Asking price" value="$1,200,000" />)
    expect(screen.getByText('Asking price')).toBeInTheDocument()
    expect(screen.getByText('$1,200,000')).toBeInTheDocument()
  })

  it('renders the label before the value in document order (stacked)', () => {
    render(<Metric label="Revenue" value="$500,000" />)
    const label = screen.getByText('Revenue')
    const value = screen.getByText('$500,000')
    // A DOM position comparison confirms the label sits above the value.
    expect(label.compareDocumentPosition(value) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})
