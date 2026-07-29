// M13 — spec 013 criteria F3/F4: the two wizard defects the golden path found.
//
// F3 — the wizard carried `type` in its form state and rendered no input for
// it, so every listing created through the UI stored `type: ''` and could never
// match M4's browse type filter.
// F4 — the Metrics step told sellers to leave fields blank that ListingCreate
// requires, and a blank serialises to "" which fails Decimal validation.
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ListingWizard } from './ListingWizard'

// The five ListingCreate requires with no default. `description`, `company_name`
// and `headline` are required too but are strings, where "" is merely empty
// rather than invalid — these five are the ones that 422.
const REQUIRED_METRICS = ['TTM revenue', 'TTM profit', 'MRR', 'Churn %', 'Customers']

describe('ListingWizard — basics and metrics (spec 013)', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('F3: the created listing carries the chosen business type, not an empty string', async () => {
    const user = userEvent.setup()
    let posted: Record<string, unknown> | null = null

    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) => {
        posted = JSON.parse(String(init?.body ?? '{}'))
        return new Response(JSON.stringify({ id: 1 }), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        })
      }),
    )

    render(<ListingWizard />)

    await user.type(screen.getByLabelText('Headline'), 'Vet practice SaaS')
    await user.type(screen.getByLabelText('Asking price'), '480000')
    await user.click(screen.getByLabelText('Business type'))
    await user.click(await screen.findByRole('option', { name: /saas/i }))
    await user.click(screen.getByRole('button', { name: 'Next' }))

    for (const label of REQUIRED_METRICS) {
      await user.type(screen.getByLabelText(new RegExp(`^${label.replace('%', '\\%')}`)), '10')
    }
    await user.click(screen.getByRole('button', { name: 'Next' }))

    await user.type(screen.getByLabelText('Company name'), 'Willowbrook Systems')
    await user.type(screen.getByLabelText('Description'), 'A description.')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Create draft' }))

    expect(posted).not.toBeNull()
    expect(posted!.type).toBe('saas')
  })

  it('F4: the metrics step marks required fields required and does not tell sellers to leave them blank', async () => {
    const user = userEvent.setup()
    render(<ListingWizard />)

    await user.type(screen.getByLabelText('Headline'), 'Vet practice SaaS')
    await user.type(screen.getByLabelText('Asking price'), '480000')
    await user.click(screen.getByLabelText('Business type'))
    await user.click(await screen.findByRole('option', { name: /saas/i }))
    await user.click(screen.getByRole('button', { name: 'Next' }))

    // Every field the API requires is marked as such, so the seller is not
    // invited to discover it via a 422.
    for (const label of REQUIRED_METRICS) {
      const field = screen.getByLabelText(new RegExp(`^${label.replace('%', '\\%')}`))
      expect(field, `${label} must be marked required`).toBeRequired()
    }

    // The specific sentence that contradicted the schema.
    const step = screen.getByRole('heading', { name: /list a business/i }).closest('div')
    expect(within(step as HTMLElement).queryByText(/leave anything you do not have blank/i)).toBeNull()
  })
})
