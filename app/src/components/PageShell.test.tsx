// UI Pass 1 shared primitives (docs/design_system_spec.md). Not yet wired
// into App.tsx (that's a later pass) -- these tests exercise the components
// standalone.
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PageContainer, PageHeader } from './PageShell'

describe('PageContainer', () => {
  it('renders its children', () => {
    render(
      <PageContainer>
        <div>page body</div>
      </PageContainer>,
    )
    expect(screen.getByText('page body')).toBeInTheDocument()
  })
})

describe('PageHeader', () => {
  it('renders the title', () => {
    render(<PageHeader title="My listings" />)
    expect(screen.getByRole('heading', { name: 'My listings' })).toBeInTheDocument()
  })

  it('renders the subtitle when provided', () => {
    render(<PageHeader title="My listings" subtitle="Everything you have for sale." />)
    expect(screen.getByText('Everything you have for sale.')).toBeInTheDocument()
  })

  it('omits the subtitle when not provided', () => {
    render(<PageHeader title="My listings" />)
    expect(screen.queryByText('Everything you have for sale.')).not.toBeInTheDocument()
  })

  it('renders the action next to the title when provided', () => {
    render(<PageHeader title="My listings" action={<button>New listing</button>} />)
    expect(screen.getByRole('button', { name: 'New listing' })).toBeInTheDocument()
  })
})
