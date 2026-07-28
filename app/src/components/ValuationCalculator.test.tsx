// M11 — the public valuation calculator (spec 011 criteria U1-U7).
//
// Written failing first: ValuationCalculator does not exist yet, so this file
// fails at import. U8 (the nav link) lives in NavBar.test.tsx, where the nav is.
//
// Every test here renders with **no token in localStorage** — the opposite of
// every other authed component test in this folder. That is the point: this is
// the one surface whose entire audience has never signed in (U1), so a test that
// seeds a session would silently stop exercising the case that matters.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ValuationCalculator } from './ValuationCalculator'

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
}

const ESTIMATE = {
  low: '300000',
  high: '500000',
  driver: 'profit',
  explanation: 'Based on 3.0-5.0x your trailing-twelve-month profit.',
  disclaimer: 'This is a rough estimate, not a valuation or financial advice.',
}

/** Fill the three required inputs with spec §6.6 row 1. */
async function fillForm() {
  await userEvent.selectOptions(await screen.findByLabelText(/business type/i), 'saas')
  await userEvent.type(screen.getByLabelText(/revenue/i), '200000')
  await userEvent.type(screen.getByLabelText(/profit/i), '100000')
}

function calculateButton() {
  return screen.getByRole('button', { name: /calculate/i })
}

describe('ValuationCalculator', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('U1: renders for a logged-out visitor without redirecting to login', async () => {
    // No token, and no fetch needed — the form must be on screen before any
    // request happens. A redirect would leave nothing to find.
    vi.stubGlobal('fetch', vi.fn())

    render(
      <MemoryRouter>
        <ValuationCalculator />
      </MemoryRouter>,
    )

    expect(await screen.findByLabelText(/business type/i)).toBeInTheDocument()
    expect(calculateButton()).toBeInTheDocument()
  })

  it('U2: submitting shows the range, the explanation and the disclaimer', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, ESTIMATE)))

    render(
      <MemoryRouter>
        <ValuationCalculator />
      </MemoryRouter>,
    )

    await fillForm()
    await userEvent.click(calculateButton())

    // The range is rendered as money, not as the raw string the API sent.
    await waitFor(() => expect(screen.getByText(/300,000/)).toBeInTheDocument())
    expect(screen.getByText(/500,000/)).toBeInTheDocument()
    expect(screen.getByText(/trailing-twelve-month profit/i)).toBeInTheDocument()
    // The disclaimer travels with the number (spec D11) — it is not UI chrome
    // the component may choose to drop.
    expect(screen.getByText(/not a valuation or financial advice/i)).toBeInTheDocument()
  })

  it('U3: shows a loading state and disables submit while in flight', async () => {
    let release: (value: Response) => void = () => {}
    const pending = new Promise<Response>((resolve) => {
      release = resolve
    })
    vi.stubGlobal('fetch', vi.fn(() => pending))

    render(
      <MemoryRouter>
        <ValuationCalculator />
      </MemoryRouter>,
    )

    await fillForm()
    await userEvent.click(calculateButton())

    // Disabled *while* the request is open — this is the double-submit guard,
    // and on a route with a 30/min cap a double-submit is half the budget.
    await waitFor(() => expect(calculateButton()).toBeDisabled())

    release(jsonResponse(200, ESTIMATE))
    await waitFor(() => expect(calculateButton()).toBeEnabled())
  })

  it('U4: renders a 422 inline against the offending field', async () => {
    // FastAPI's native field-level shape (error_handling.md §1) — the frontend
    // maps `loc` to a field. Asserting the message lands *next to the input*
    // rather than in a banner is what makes this a mapping test rather than a
    // "some error appeared" test.
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(422, {
          detail: [
            {
              loc: ['body', 'ttm_profit'],
              msg: 'profit cannot exceed revenue',
              type: 'value_error',
            },
          ],
        }),
      ),
    )

    render(
      <MemoryRouter>
        <ValuationCalculator />
      </MemoryRouter>,
    )

    await fillForm()
    await userEvent.click(calculateButton())

    const profitInput = await screen.findByLabelText(/profit/i)
    await waitFor(() => expect(profitInput).toHaveAccessibleDescription(/cannot exceed revenue/i))
  })

  it('U5: renders a 429 in plain language, not a raw error code', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(429, { detail: 'Too many requests', code: 'rate_limited' }, {
          'Retry-After': '60',
        }),
      ),
    )

    render(
      <MemoryRouter>
        <ValuationCalculator />
      </MemoryRouter>,
    )

    await fillForm()
    await userEvent.click(calculateButton())

    await waitFor(() => expect(screen.getByText(/too fast|try again/i)).toBeInTheDocument())
    // The machine slug is for our branching, never for a stranger's screen.
    expect(screen.queryByText(/rate_limited/)).not.toBeInTheDocument()
  })

  it('U6: capturing the email confirms, and the estimate stays on screen', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/leads')) return jsonResponse(201, ESTIMATE)
      return jsonResponse(200, ESTIMATE)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <MemoryRouter>
        <ValuationCalculator />
      </MemoryRouter>,
    )

    await fillForm()
    await userEvent.click(calculateButton())
    await waitFor(() => expect(screen.getByText(/300,000/)).toBeInTheDocument())

    await userEvent.type(await screen.findByLabelText(/email/i), 'founder@example.com')
    await userEvent.click(screen.getByRole('button', { name: /send|email|get/i }))

    await waitFor(() => expect(screen.getByText(/on its way|thank|got it/i)).toBeInTheDocument())
    // Taking the estimate away the moment someone hands over their address is a
    // bait-and-switch; the number they came for stays put.
    expect(screen.getByText(/300,000/)).toBeInTheDocument()
  })

  it('U7: shows an initial empty state rather than a zeroed estimate', async () => {
    vi.stubGlobal('fetch', vi.fn())

    render(
      <MemoryRouter>
        <ValuationCalculator />
      </MemoryRouter>,
    )

    // A rendered "$0 - $0" before anyone has typed anything looks like an
    // answer, and the answer it looks like is "your business is worthless".
    expect(screen.queryByText(/\$0/)).not.toBeInTheDocument()
    expect(screen.queryByText(/disclaimer/i)).not.toBeInTheDocument()
    // The email capture belongs to a result, so it cannot precede one.
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
  })
})
