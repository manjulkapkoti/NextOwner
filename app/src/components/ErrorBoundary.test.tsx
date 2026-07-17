// M1 — ErrorBoundary catches a render crash (spec 001 acceptance criterion H4).
// A render-time throw must show the fallback, never a white screen.
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ErrorBoundary } from './ErrorBoundary'

function Boom(): JSX.Element {
  throw new Error('render exploded')
}

describe('ErrorBoundary', () => {
  it('renders a fallback instead of crashing the tree', () => {
    // React logs the caught error; silence it so the test output stays clean.
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    )
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    spy.mockRestore()
  })
})
