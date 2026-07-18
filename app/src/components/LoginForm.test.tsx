// M1 — login form shows inline 422 errors (spec 001 acceptance criterion H3).
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LoginForm } from './LoginForm'

describe('LoginForm', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => vi.unstubAllGlobals())

  it('renders a 422 field error inline on the email field', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              detail: [
                { loc: ['body', 'email'], msg: 'value is not a valid email address', type: 'value_error.email' },
              ],
            }),
            { status: 422, headers: { 'Content-Type': 'application/json' } },
          ),
      ),
    )
    render(
      <MemoryRouter>
        <LoginForm />
      </MemoryRouter>,
    )
    // `delay: null` — no per-keystroke pause; nothing here asserts on typing
    // speed, and the pause is what pushes these past the 5s default timeout.
    const user = userEvent.setup({ delay: null })
    await user.type(screen.getByLabelText(/email/i), 'not-an-email')
    await user.type(screen.getByLabelText(/password/i), 'whatever')
    await user.click(screen.getByRole('button', { name: /log in/i }))
    await waitFor(() =>
      expect(screen.getByText(/not a valid email address/i)).toBeInTheDocument(),
    )
  })
})
