// M1 — route guard redirects a logged-out visitor (spec 001 acceptance criterion H1).
// Client-side guards are UX only — the server gate is the real boundary.
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { RequireAuth } from './RequireAuth'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<div>Login page</div>} />
        <Route
          path="/sell"
          element={
            <RequireAuth>
              <div>Seller area</div>
            </RequireAuth>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RequireAuth', () => {
  beforeEach(() => localStorage.clear())

  it('redirects a logged-out visitor from /sell to /login', () => {
    renderAt('/sell')
    expect(screen.getByText('Login page')).toBeInTheDocument()
    expect(screen.queryByText('Seller area')).not.toBeInTheDocument()
  })

  it('renders the protected content when a token is present', () => {
    localStorage.setItem('token', 'a.b.c')
    renderAt('/sell')
    expect(screen.getByText('Seller area')).toBeInTheDocument()
  })
})
