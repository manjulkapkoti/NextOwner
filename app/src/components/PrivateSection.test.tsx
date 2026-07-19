// M5 — the unlocked private section (spec 005 criterion J3; plan.md §
// Frontend: "renders `ListingPrivateRead` + the document list once
// unlocked").
//
// The security rules that apply to any user-authored content apply here too
// (constitution / this agent's rules): never dangerouslySetInnerHTML, and
// scrub `website_url` before linking it — a seller's own field is not
// automatically safe to interpolate into an href. Document downloads must
// carry the caller's credentials (they are gated by the same
// `require_private_access` as the JSON payload — plan.md § Endpoints), so a
// plain unauthenticated `<a href>` cannot be the whole mechanism.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PrivateSection } from './PrivateSection'

const PRIVATE_DATA = {
  company_name: 'Acme Internal Tools LLC',
  website_url: 'https://acme.example.com',
  detailed_financials: 'Full P&L available on request — trailing 12mo net margin 24%.',
}

const DOCUMENTS = [{ id: 5, filename: 'financials.pdf' }]

function stubDownload() {
  const fetchMock = vi.fn<typeof fetch>(
    async () =>
      new Response(new Blob(['file bytes'], { type: 'application/pdf' }), {
        status: 200,
        headers: { 'Content-Type': 'application/pdf' },
      }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('PrivateSection', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'a.b.c')
    // jsdom has no object-URL implementation; stub it so a real
    // createObjectURL()+<a download> save trigger cannot crash the test
    // regardless of how the component implements "downloadable".
    vi.stubGlobal('URL', Object.assign(URL, {
      createObjectURL: vi.fn(() => 'blob:mock'),
      revokeObjectURL: vi.fn(),
    }))
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('J3: renders the unlocked company name, website and detailed financials', () => {
    stubDownload()
    render(<PrivateSection listingId={7} data={PRIVATE_DATA} documents={DOCUMENTS} />)

    expect(screen.getByText(PRIVATE_DATA.company_name)).toBeInTheDocument()
    expect(screen.getByText(/full p&l available on request/i)).toBeInTheDocument()
    const link = screen.getByRole('link', { name: /acme\.example\.com/i })
    expect(link).toHaveAttribute('href', PRIVATE_DATA.website_url)
  })

  it("J3: each document is downloadable — clicking it fetches the file with the caller's credentials", async () => {
    const fetchMock = stubDownload()
    const user = userEvent.setup({ delay: null })
    render(<PrivateSection listingId={7} data={PRIVATE_DATA} documents={DOCUMENTS} />)

    await user.click(screen.getByRole('button', { name: /financials\.pdf/i }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit | undefined]
    expect(String(url)).toBe('/api/listings/7/documents/5')
    const headers = (init?.headers ?? {}) as Record<string, string>
    expect(headers.Authorization).toBe('Bearer a.b.c')
  })

  it('scrubs an unsafe website_url scheme rather than linking it', () => {
    stubDownload()
    const { container } = render(
      <PrivateSection
        listingId={7}
        data={{ ...PRIVATE_DATA, website_url: 'javascript:alert(1)' }}
        documents={DOCUMENTS}
      />,
    )

    expect(screen.queryByRole('link', { name: /javascript:/i })).toBeNull()
    expect(container.querySelector('a[href^="javascript:"]')).toBeNull()
  })
})
