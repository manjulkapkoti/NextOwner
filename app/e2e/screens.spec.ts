// Captures every screen at three widths, so the UI can be looked at instead of
// described. These write artefacts rather than asserting — the point is to give
// whoever (or whatever) is building the UI a way to see its own work.
//
// Output: e2e/__screens__/<screen>-<width>.png (gitignored).
//
// The three widths are the ones the design system actually names
// (docs/design_system_spec.md §3): the 360px layout floor, the 768px tablet
// breakpoint where the nav collapses, and a normal desktop.
import { test, expect, type Page } from '@playwright/test'

const WIDTHS = [
  { name: '360', width: 360, height: 780 }, // the layout floor
  { name: '768', width: 768, height: 900 }, // nav collapse boundary
  { name: '1280', width: 1280, height: 900 }, // desktop
]

// Public screens need no session. The authed ones are covered by seeding a
// token and stubbing the API, so this stays a UI check and does not depend on
// a running backend.
const PUBLIC_SCREENS = [
  { name: 'landing', path: '/' },
  { name: 'login', path: '/login' },
  { name: 'signup', path: '/register' },
]

const AUTHED_SCREENS = [
  { name: 'dashboard-empty', path: '/my-listings', listings: [] },
  {
    name: 'dashboard-list',
    path: '/my-listings',
    listings: [
      { id: 1, headline: 'Profitable B2B SaaS in the HR space', status: 'live' },
      { id: 2, headline: 'Niche ecommerce store, 4 years old', status: 'draft' },
      { id: 3, headline: 'Content site with 80k monthly visits', status: 'under_offer' },
    ],
  },
  { name: 'wizard', path: '/sell', listings: [] },
]

// UI Pass 2 — the marketplace browse grid and a listing's detail page, the two
// screens the pass restyled most (ListingCard, BrowseListings, ListingDetail).
// Both are public routes, stubbed the same way the a11y spec's marketplace
// scan already is, so this stays a UI check independent of a running backend.
const BROWSE_ITEM_A = {
  id: 42,
  type: 'saas',
  headline: 'Profitable B2B scheduling SaaS',
  description:
    'A small, profitable scheduling tool for clinics, with steady growth and low monthly churn.',
  asking_price: '500000.00',
  ttm_revenue: '200000.00',
  ttm_profit: '120000.00',
  mrr: '18000.00',
  churn_pct: '2.50',
  customers: 340,
  published_at: '2026-07-01T00:00:00Z',
}

const BROWSE_ITEM_B = {
  ...BROWSE_ITEM_A,
  id: 43,
  type: 'ecommerce',
  headline: 'DTC specialty coffee subscription',
}

for (const vp of WIDTHS) {
  test(`screen: browse @ ${vp.name}`, async ({ page }) => {
    await page.route('**/api/listings*', (route) =>
      route.fulfill({
        json: { items: [BROWSE_ITEM_A, BROWSE_ITEM_B], total: 2, limit: 20, offset: 0 },
      }),
    )
    await page.setViewportSize({ width: vp.width, height: vp.height })
    await page.goto('/browse')
    await page.getByText(BROWSE_ITEM_A.headline).waitFor()
    await settle(page)
    await page.screenshot({ path: `e2e/__screens__/browse-${vp.name}.png`, fullPage: true })
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    )
    expect(overflow, `browse scrolls horizontally at ${vp.name}px`).toBe(false)
  })

  test(`screen: browse-detail @ ${vp.name}`, async ({ page }) => {
    await page.route('**/api/listings/*', (route) => route.fulfill({ json: BROWSE_ITEM_A }))
    await page.setViewportSize({ width: vp.width, height: vp.height })
    await page.goto(`/browse/${BROWSE_ITEM_A.id}`)
    await page.getByText(BROWSE_ITEM_A.headline).waitFor()
    await settle(page)
    await page.screenshot({ path: `e2e/__screens__/browse-detail-${vp.name}.png`, fullPage: true })
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    )
    expect(overflow, `browse-detail scrolls horizontally at ${vp.name}px`).toBe(false)
  })
}

async function stubAuth(page: Page, listings: unknown[]) {
  await page.addInitScript(() => localStorage.setItem('token', 'e2e.fake.token'))
  await page.route('**/api/my/listings', (route) =>
    route.fulfill({ json: listings as object[] }),
  )
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ json: { id: 1, email: 'seller@example.com', is_seller: true } }),
  )
}

// Fonts must be loaded before a screenshot, or the capture shows the fallback
// face — which would make every wordmark check meaningless.
async function settle(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(150)
}

for (const screen of PUBLIC_SCREENS) {
  for (const vp of WIDTHS) {
    test(`screen: ${screen.name} @ ${vp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height })
      await page.goto(screen.path)
      await settle(page)
      await page.screenshot({
        path: `e2e/__screens__/${screen.name}-${vp.name}.png`,
        fullPage: true,
      })
      // The one assertion worth making here: nothing may overflow sideways.
      // A horizontal scrollbar at or above the 360px floor is the exact defect
      // the floor exists to prevent.
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      )
      expect(overflow, `${screen.name} scrolls horizontally at ${vp.name}px`).toBe(false)
    })
  }
}

for (const screen of AUTHED_SCREENS) {
  for (const vp of WIDTHS) {
    test(`screen: ${screen.name} @ ${vp.name}`, async ({ page }) => {
      await stubAuth(page, screen.listings)
      await page.setViewportSize({ width: vp.width, height: vp.height })
      await page.goto(screen.path)
      await settle(page)
      await page.screenshot({
        path: `e2e/__screens__/${screen.name}-${vp.name}.png`,
        fullPage: true,
      })
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      )
      expect(overflow, `${screen.name} scrolls horizontally at ${vp.name}px`).toBe(false)
    })
  }
}
