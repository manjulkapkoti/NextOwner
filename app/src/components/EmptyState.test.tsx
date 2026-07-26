// UI Pass 1 shared primitive (docs/design_system_spec.md).
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { EmptyState } from './EmptyState'

describe('EmptyState', () => {
  it('renders the message', () => {
    render(<EmptyState message="No watchlist entries yet." />)
    expect(screen.getByText('No watchlist entries yet.')).toBeInTheDocument()
  })

  it('renders no button when no action is passed', () => {
    render(<EmptyState message="Nothing here yet." />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('renders and wires up the action button when passed', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(<EmptyState message="No saved searches yet." action={{ label: 'Create a search', onClick }} />)

    const button = screen.getByRole('button', { name: 'Create a search' })
    expect(button).toBeInTheDocument()
    await user.click(button)
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})
