// M8 — account lifecycle pages (spec 008 criteria J8, J9, J10).
// Written failing first: none of these three pages exist yet.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ForgotPasswordPage } from './ForgotPasswordPage'
import { ResetPasswordPage } from './ResetPasswordPage'
import { VerifyEmailPage } from './VerifyEmailPage'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('ForgotPasswordPage', () => {
  // The UI must not leak what the API deliberately refuses to (spec G2): the
  // confirmation is identical whether or not the address belongs to anyone.
  it('J8: shows the same confirmation for any address submitted', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(202, { status: 'accepted' })))

    const messages: string[] = []
    for (const address of ['real@example.com', 'nobody@example.com']) {
      const view = render(
        <MemoryRouter>
          <ForgotPasswordPage />
        </MemoryRouter>,
      )
      await userEvent.type(screen.getByLabelText(/email/i), address)
      await userEvent.click(screen.getByRole('button', { name: /send/i }))
      messages.push((await screen.findByRole('status')).textContent ?? '')
      view.unmount()
    }

    expect(messages[0]).toBe(messages[1])
    expect(messages[0]).not.toBe('')
  })
})

describe('ResetPasswordPage', () => {
  it('J9: displays a 422 from the API inline on the password field', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(422, {
          detail: [
            {
              loc: ['body', 'password'],
              msg: 'String should have at least 12 characters',
              type: 'string_too_short',
            },
          ],
        }),
      ),
    )

    render(
      <MemoryRouter initialEntries={['/reset-password?token=abc']}>
        <ResetPasswordPage />
      </MemoryRouter>,
    )

    await userEvent.type(screen.getByLabelText(/new password/i), 'short')
    await userEvent.click(screen.getByRole('button', { name: /reset password/i }))

    expect(await screen.findByText(/at least 12 characters/i)).toBeInTheDocument()
  })
})

describe('VerifyEmailPage', () => {
  it('J10: a rejected token shows a failure state with a resend affordance', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(400, { detail: 'Invalid or expired link', code: 'invalid_token' }),
      ),
    )

    render(
      <MemoryRouter initialEntries={['/verify-email?token=dead']}>
        <VerifyEmailPage />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /resend/i })).toBeInTheDocument()
  })
})
