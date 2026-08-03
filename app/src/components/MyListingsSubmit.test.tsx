// M13 — spec 013 criteria F1/F2: the submit-for-review action.
//
// Why this is a new file rather than additions to MyListings.test.tsx: the spec
// coverage checker attributes a test file to a milestone by the tag in its
// first six lines, so criteria added to the M2 file would count for spec 002.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MyListings } from './MyListings'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('MyListings — submit for review (spec 013)', () => {
  beforeEach(() => localStorage.setItem('token', 'a.b.c'))
  afterEach(() => vi.unstubAllGlobals())

  it('F1: submitting a draft moves it to In review and withdraws the action', async () => {
    const user = userEvent.setup()
    let submitted = false

    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === 'POST' && String(url).includes('/listings/7/submit')) {
          submitted = true
          return json({ id: 7, headline: 'Vet SaaS', status: 'pending_review' })
        }
        return json([
          { id: 7, headline: 'Vet SaaS', status: submitted ? 'pending_review' : 'draft' },
        ])
      }),
    )

    render(<MyListings />)
    const action = await screen.findByRole('button', { name: /submit for review/i })
    await user.click(action)

    await waitFor(() => expect(screen.getByText('In review')).toBeInTheDocument())
    expect(submitted).toBe(true)
    // The transition is one-way, so offering it again is offering a 409.
    expect(screen.queryByRole('button', { name: /submit for review/i })).not.toBeInTheDocument()
  })

  it('F2: the action is absent on every non-draft row', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        json([
          { id: 1, headline: 'Already live', status: 'live' },
          { id: 2, headline: 'Waiting on review', status: 'pending_review' },
          { id: 3, headline: 'Closed deal', status: 'sold', final_price: '445000.00' },
        ]),
      ),
    )

    render(<MyListings />)
    await screen.findByText('Already live')

    // Hiding the action is UX; the server's 409 is the control (spec 013
    // § Security & abuse). This asserts the UX half only.
    expect(screen.queryByRole('button', { name: /submit for review/i })).not.toBeInTheDocument()
  })
})
