// Registration form (FR-1/FR-2). Mirrors LoginForm's states: loading, inline
// 422 field errors, a form-level error for non-field failures (409 duplicate
// email), and the golden path.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { RegisterForm } from './RegisterForm'

function renderForm() {
  return render(
    <MemoryRouter initialEntries={['/register']}>
      <Routes>
        <Route path="/register" element={<RegisterForm />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

async function fillAndSubmit(email = 'alice@example.com', password = 'correct horse battery staple') {
  await userEvent.type(screen.getByLabelText(/email/i), email)
  await userEvent.type(screen.getByLabelText(/password/i), password)
  await userEvent.click(screen.getByRole('button', { name: /create account/i }))
}

describe('RegisterForm', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => vi.unstubAllGlobals())

  it('creates the account and navigates to /login on success', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ id: 1, email: 'alice@example.com' }), {
            status: 201,
            headers: { 'Content-Type': 'application/json' },
          }),
      ),
    )
    renderForm()
    await fillAndSubmit()
    await waitFor(() => expect(screen.getByText('Login page')).toBeInTheDocument())
    expect(fetch).toHaveBeenCalledWith('/api/auth/register', expect.objectContaining({ method: 'POST' }))
  })

  it('shows inline field errors on a 422 response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              detail: [
                { loc: ['body', 'password'], msg: 'String should have at least 8 characters', type: 'string_too_short' },
              ],
            }),
            { status: 422, headers: { 'Content-Type': 'application/json' } },
          ),
      ),
    )
    renderForm()
    await fillAndSubmit('alice@example.com', 'short')
    await waitFor(() =>
      expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument(),
    )
  })

  it('shows a form-level error for a 409 duplicate email', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ detail: 'Email already registered', code: 'email_taken' }),
            { status: 409, headers: { 'Content-Type': 'application/json' } },
          ),
      ),
    )
    renderForm()
    await fillAndSubmit()
    await waitFor(() =>
      expect(screen.getByText(/already registered/i)).toBeInTheDocument(),
    )
  })
})
