// M8 — saved searches (spec 008 criterion J7).
// Written failing first: SavedSearches does not exist yet.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SavedSearches } from './SavedSearches'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('SavedSearches', () => {
  beforeEach(() => localStorage.setItem('token', 'a.b.c'))
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('J7: saving a search adds it to the list', async () => {
    const rows: unknown[] = []
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') {
        const created = {
          id: 1,
          name: 'Profitable SaaS',
          filters: { type: 'saas' },
          created_at: '2026-07-25T10:00:00Z',
        }
        rows.push(created)
        return jsonResponse(201, created)
      }
      return jsonResponse(200, [...rows])
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <MemoryRouter>
        <SavedSearches />
      </MemoryRouter>,
    )

    await userEvent.type(await screen.findByLabelText(/name/i), 'Profitable SaaS')
    await userEvent.click(screen.getByRole('button', { name: /save search/i }))

    await waitFor(() =>
      expect(screen.getByText('Profitable SaaS')).toBeInTheDocument(),
    )
  })
})
