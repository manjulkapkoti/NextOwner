// M2 — the seller dashboard (spec 002 acceptance criterion H2).
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MyListings } from './MyListings'

describe('MyListings', () => {
  beforeEach(() => localStorage.setItem('token', 'a.b.c'))
  afterEach(() => vi.unstubAllGlobals())

  it('renders the empty state when the seller has no listings', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } })),
    )
    render(<MyListings />)
    await waitFor(() => expect(screen.getByText(/no listings yet/i)).toBeInTheDocument())
  })

  it('lists the seller listings with their status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify([{ id: 1, headline: 'My SaaS', status: 'draft' }]),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
      ),
    )
    render(<MyListings />)
    await waitFor(() => expect(screen.getByText('My SaaS')).toBeInTheDocument())
    expect(screen.getByText(/draft/i)).toBeInTheDocument()
  })

// M3 (spec 003 criterion C6) — the API returning the reason is not the same as
// the seller being able to read it.
it('C6: shows the rejection reason on a rejected listing', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () =>
        new Response(
          JSON.stringify([
            {
              id: 1,
              headline: 'My SaaS',
              status: 'rejected',
              rejection_reason: 'Financials do not reconcile with the stated MRR.',
            },
          ]),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
    ),
  )
  render(<MyListings />)
  await waitFor(() => expect(screen.getByText('My SaaS')).toBeInTheDocument())
  expect(screen.getByText(/do not reconcile/i)).toBeInTheDocument()
})
})
