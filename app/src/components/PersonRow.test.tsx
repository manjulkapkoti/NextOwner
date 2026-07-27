// UI Pass 4 — the shared "person row" pattern used by AccessRequestQueue,
// ConversationList, and NotificationInbox.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PersonRow } from './PersonRow'

describe('PersonRow', () => {
  it('renders avatar, title, meta and chip', () => {
    render(
      <PersonRow
        avatar={<span data-testid="avatar">A</span>}
        title="Jordan Buyer"
        meta="Budget: 250,000"
        chip={<span>Requested</span>}
      />,
    )

    expect(screen.getByTestId('avatar')).toBeInTheDocument()
    expect(screen.getByText('Jordan Buyer')).toBeInTheDocument()
    expect(screen.getByText('Budget: 250,000')).toBeInTheDocument()
    expect(screen.getByText('Requested')).toBeInTheDocument()
  })

  it('renders no chip element when chip is omitted', () => {
    const { container } = render(<PersonRow avatar={<span>A</span>} title="No chip here" />)
    expect(container.querySelectorAll('.MuiChip-root').length).toBe(0)
  })

  it('renders actions below the meta line', () => {
    render(
      <PersonRow
        avatar={<span>A</span>}
        title="Row with actions"
        actions={<button>Approve</button>}
      />,
    )
    expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument()
  })

  it('wraps the row in a clickable area when onClick is passed, and fires it', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(<PersonRow avatar={<span>A</span>} title="Clickable row" onClick={onClick} />)

    await user.click(screen.getByText('Clickable row'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('does not render a clickable area when onClick is omitted', () => {
    render(<PersonRow avatar={<span>A</span>} title="Not clickable" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('forwards testId and dataAttrs to the outer row', () => {
    render(
      <PersonRow
        avatar={<span>A</span>}
        title="Row with data attrs"
        testId="row-11"
        dataAttrs={{ 'data-unread': 'true' }}
      />,
    )
    const row = screen.getByTestId('row-11')
    expect(row).toHaveAttribute('data-unread', 'true')
  })
})
