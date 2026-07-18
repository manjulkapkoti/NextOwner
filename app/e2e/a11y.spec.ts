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

test('a11y: listing wizard', async ({ page }) => {
  await stubSeller(page, [])
  await page.goto('/sell')
  const results = await scan(page)
  expect(
    results.violations,
    results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length} nodes)`).join('\n'),
  ).toEqual([])
})
