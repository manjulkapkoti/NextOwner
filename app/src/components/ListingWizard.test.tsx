// M2 — listing wizard step validation (spec 002 acceptance criterion H1).
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { ListingWizard } from './ListingWizard'

describe('ListingWizard', () => {
  beforeEach(() => localStorage.clear())

  it('blocks advancing and shows an inline error when asking price is not positive', async () => {
    render(<ListingWizard />)
    // First step collects the asking price; enter a non-positive value.
    await userEvent.type(screen.getByLabelText(/asking price/i), '0')
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(await screen.findByText(/asking price must be greater than 0/i)).toBeInTheDocument()
  })
})
