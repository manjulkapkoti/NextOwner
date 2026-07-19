// Accessibility assertions — these FAIL the run, unlike the screenshots.
//
// The design system commits to WCAG AA (docs/design_system_spec.md §8), and
// that commitment has already been broken once by a spec that *required* AA
// while specifying a focus ring at 1.80:1. A machine catches that in a second;
// a human caught it only because contrast was measured by hand.
//
// Scope: the WCAG 2 A/AA rule sets. Best-practice rules are excluded, since
// they are opinions rather than the standard we committed to.
import AxeBuilder from '@axe-core/playwright'
import { test, expect, type Page } from '@playwright/test'

const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

const PUBLIC_SCREENS = [
  { name: 'landing', path: '/' },
  { name: 'login', path: '/login' },
  { name: 'signup', path: '/register' },
]

async function stubSeller(page: Page, listings: unknown[]) {
  await page.addInitScript(() => localStorage.setItem('token', 'e2e.fake.token'))
  await page.route('**/api/my/listings', (route) => route.fulfill({ json: listings as object[] }))
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ json: { id: 1, email: 'seller@example.com', is_seller: true } }),
  )
}

async function scan(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  return (
    new AxeBuilder({ page })
      .withTags(TAGS)
      // The wordmark only. WCAG 1.4.3 exempts "text that is part of a logo or
      // brand name" from the contrast minimum, and the brand orange is 2.94:1
      // on white — correct for a mark, a real failure anywhere else. Excluding
      // the element keeps the exemption narrow: the contrast rule still runs
      // everywhere else on the page, which is the point.
      .exclude('[data-logotype]')
      .analyze()
  )
}

// Reported at the width where problems are most likely: the layout floor, where
// targets are tightest and text is smallest.
test.use({ viewport: { width: 360, height: 780 } })

for (const screen of PUBLIC_SCREENS) {
  test(`a11y: ${screen.name}`, async ({ page }) => {
    await page.goto(screen.path)
    const results = await scan(page)
    expect(
      results.violations,
      results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length} nodes)`).join('\n'),
    ).toEqual([])
  })
}

// M4's marketplace — the most-visited public screen in the product, and the
// only one an anonymous stranger reaches with real data on it. Scanned with
// results present rather than empty: an empty grid would skip the cards, which
// carry most of the screen's text and contrast.
test('a11y: marketplace browse with results', async ({ page }) => {
  const card = (id: number, headline: string, type: string) => ({
    id,
    type,
    headline,
    description: 'A small, profitable business with steady revenue and low churn.',
    asking_price: '500000.00',
    ttm_revenue: '200000.00',
    ttm_profit: '120000.00',
    mrr: '18000.00',
    churn_pct: '2.50',
    customers: 340,
    published_at: '2026-07-01T00:00:00Z',
  })
  await page.route('**/api/listings*', (route) =>
    route.fulfill({
      json: {
        items: [
          card(1, 'Profitable B2B scheduling SaaS', 'saas'),
          card(2, 'DTC specialty coffee subscription', 'ecommerce'),
        ],
        total: 2,
        limit: 20,
        offset: 0,
      },
    }),
  )
  await page.goto('/browse')
  await page.getByText('Profitable B2B scheduling SaaS').waitFor()
  const results = await scan(page)
  expect(
    results.violations,
    results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length} nodes)`).join('\n'),
  ).toEqual([])
})

test('a11y: dashboard with listings', async ({ page }) => {
  await stubSeller(page, [
    { id: 1, headline: 'Profitable B2B SaaS in the HR space', status: 'live' },
    { id: 2, headline: 'Niche ecommerce store, 4 years old', status: 'draft' },
  ])
  await page.goto('/my-listings')
  const results = await scan(page)
  expect(
    results.violations,
    results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length} nodes)`).join('\n'),
  ).toEqual([])
})

// M3's curation queue. An admin-only screen still gets scanned — "only staff
// see it" is not an accessibility exemption, and it is the screen with the
// densest controls in the product so far.
test('a11y: admin curation queue', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('token', 'e2e.fake.token'))
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ json: { id: 1, email: 'admin@example.com', is_admin: true } }),
  )
  await page.route('**/api/admin/listings**', (route) =>
    route.fulfill({
      json: [
        {
          id: 7,
          headline: 'Profitable B2B scheduling SaaS',
          type: 'saas',
          asking_price: '500000.00',
          status: 'pending_review',
          created_at: '2026-07-19T10:00:00Z',
          company_name: 'Acme Internal Tools LLC',
          website_url: 'https://acme.example.com',
        },
      ],
    }),
  )
  await page.goto('/admin')
  const results = await scan(page)
  expect(
    results.violations,
    results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length} nodes)`).join('\n'),
  ).toEqual([])
})

test('a11y: listing wizard', async ({ page }) => {
  await stubSeller(page, [])
  await page.goto('/sell')
  const results = await scan(page)
  expect(
    results.violations,
    results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length} nodes)`).join('\n'),
  ).toEqual([])
})
