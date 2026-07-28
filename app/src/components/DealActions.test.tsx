// M12 — the seller's deal-close actions (spec 012 criteria F1-F8, FR-8).
//
// The two irreversible buttons on the whole product. Everything here exists to
// make "irreversible" visible before it happens: the price is rendered, never
// entered (F1 — spec D4's server-derivation, at the UI layer), and both paths
// go through a confirmation the seller has to read (F3/F4).
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DealActions } from './DealActions'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const UNDER_OFFER = {
  id: 7,
  status: 'under_offer',
  headline: 'Profitable B2B scheduling SaaS',
  final_price: null as string | null,
  sold_at: null as string | null,
}

const ACCEPTED_PRICE = '480000.00'

function renderActions(listing = UNDER_OFFER, acceptedPrice: string | null = ACCEPTED_PRICE) {
  const onChange = vi.fn()
  render(<DealActions listing={listing} acceptedPrice={acceptedPrice} onChange={onChange} />)
  return { onChange }
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, { ...UNDER_OFFER, status: 'sold' })))
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('DealActions', () => {
  it('F1 — offers both actions and shows the price that will be recorded, read-only', () => {
    renderActions()

    expect(screen.getByRole('button', { name: /mark as sold/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /deal fell through/i })).toBeInTheDocument()
    // The price is displayed, never entered — the server derives it from the
    // accepted offer and the UI must not imply otherwise (spec D4).
    expect(screen.getByText(/480,?000/)).toBeInTheDocument()
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it.each(['live', 'sold', 'paused', 'draft'])(
    'F2 — renders no deal actions while the listing is %s',
    (status) => {
      renderActions({ ...UNDER_OFFER, status })

      expect(screen.queryByRole('button', { name: /mark as sold/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /deal fell through/i })).not.toBeInTheDocument()
    },
  )

  it('F3 — confirms before closing the deal, and sends nothing until confirmed', async () => {
    const user = userEvent.setup()
    renderActions()

    await user.click(screen.getByRole('button', { name: /mark as sold/i }))

    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent(/480,?000/)
    expect(dialog).toHaveTextContent(/cannot be undone|final|permanent/i)
    expect(fetch).not.toHaveBeenCalled()
  })

  it('F4 — cancelling the confirmation sends no request', async () => {
    const user = userEvent.setup()
    const { onChange } = renderActions()

    await user.click(screen.getByRole('button', { name: /mark as sold/i }))
    await screen.findByRole('dialog')
    await user.click(screen.getByRole('button', { name: /cancel/i }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(fetch).not.toHaveBeenCalled()
    expect(onChange).not.toHaveBeenCalled()
  })

  it('F5 — a confirmed close posts to mark-sold and reports the change upward', async () => {
    const user = userEvent.setup()
    const { onChange } = renderActions()

    await user.click(screen.getByRole('button', { name: /mark as sold/i }))
    await screen.findByRole('dialog')
    await user.click(screen.getByRole('button', { name: /^mark as sold$/i, hidden: false }))

    await waitFor(() => expect(onChange).toHaveBeenCalled())
    const [url, init] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(String(url)).toContain('/api/listings/7/mark-sold')
    expect((init as RequestInit).method).toBe('POST')
    // No body: every field the server needs it derives itself (spec S1).
    expect((init as RequestInit).body ?? null).toBeNull()
  })

  it('F8 — the fell-through action posts to relist', async () => {
    const user = userEvent.setup()
    const { onChange } = renderActions()

    await user.click(screen.getByRole('button', { name: /deal fell through/i }))
    await screen.findByRole('dialog')
    await user.click(screen.getByRole('button', { name: /put back on the market/i }))

    await waitFor(() => expect(onChange).toHaveBeenCalled())
    expect(String((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0])).toContain(
      '/api/listings/7/relist',
    )
  })

  it('F6 — a 409 renders the error contract message inline instead of crashing', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(409, { detail: 'Cannot go from live to sold', code: 'invalid_transition' }),
      ),
    )
    const user = userEvent.setup()
    const { onChange } = renderActions()

    await user.click(screen.getByRole('button', { name: /mark as sold/i }))
    await screen.findByRole('dialog')
    await user.click(screen.getByRole('button', { name: /^mark as sold$/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/cannot go from live to sold/i)
    // The status is the server's to change — no optimistic flip to `sold`.
    expect(onChange).not.toHaveBeenCalled()
    // The dialog stays open and re-armed: a refused close must leave the seller
    // somewhere they can read the reason and retry, not dumped back to a card
    // whose alert the modal had been hiding.
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^mark as sold$/i })).toBeEnabled()
  })

  // Spec 012 F7 was written as "both actions are disabled" — the wrong noun for
  // a modal confirm flow. While a request is in flight the confirmation dialog
  // is open, and MUI's modal makes everything behind it inert and
  // aria-hidden — so the two trigger buttons are already unreachable, and
  // asserting on them tests the modal rather than the guard. The property the
  // criterion is protecting is *no double submit*, and the only element a
  // second click can reach is the confirm button. Spec amended deliberately
  // (`/run-milestone`: fix the spec, don't weaken the test), and the exactly-one
  // -fetch assertion below is what actually pins the property.
  it('F7 — the confirm action is disabled while a request is in flight', async () => {
    let release: (value: Response) => void = () => {}
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            release = resolve
          }),
      ),
    )
    const user = userEvent.setup()
    renderActions()

    await user.click(screen.getByRole('button', { name: /mark as sold/i }))
    const dialog = await screen.findByRole('dialog')
    const confirm = within(dialog).getByRole('button', { name: /^mark as sold$/i })
    await user.click(confirm)

    await waitFor(() => expect(confirm).toBeDisabled())
    expect(within(dialog).getByRole('button', { name: /cancel/i })).toBeDisabled()
    // A second click on the still-mounted confirm sends nothing. `fireEvent`
    // rather than `user.click`, deliberately: userEvent *refuses* to click a
    // `pointer-events: none` element and throws, which would pass this test for
    // the wrong reason — the assertion would then be about the testing library,
    // not about the guard. Dispatching the event directly is the harsher check:
    // the handler is reachable and still must not fire a second request.
    fireEvent.click(confirm)
    expect(fetch).toHaveBeenCalledTimes(1)
    release(jsonResponse(200, { ...UNDER_OFFER, status: 'sold' }))
  })
})
