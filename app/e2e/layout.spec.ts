// Layout invariants — the deterministic alternative to pixel baselines.
//
// Screenshot diffing would catch these, but not portably: this project is
// developed on Windows and runs CI on Linux, and font antialiasing alone makes
// the same page render differently. The usual answer is a Playwright Docker
// image, which the constitution rules out ("no Docker required"). Baselines
// would then be Linux PNGs nobody can regenerate locally, or a constant source
// of false diffs — and a check that cries wolf gets ignored, which is how the
// "flaky" RegisterForm test trained everyone to re-run instead of investigate.
//
// So these assert the *properties* the pixels would have protected. Each one
// corresponds to a defect this project actually shipped and a human had to
// catch by eye.
import { test, expect, type Page } from '@playwright/test'

const WIDTHS = [360, 768, 1280]

async function settle(page: Page) {
  await page.evaluate(() => document.fonts.ready)
}

// DEFECT: the authed nav wrapped onto a second row on a phone — brand plus
// three labelled buttons did not fit. Wrapping is invisible to every other
// check here, because nothing overflows: the row just becomes two rows.
for (const width of WIDTHS) {
  test(`nav stays on one row @ ${width}`, async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('token', 'e2e.fake.token'))
    await page.route('**/api/my/listings', (route) => route.fulfill({ json: [] }))
    await page.route('**/api/auth/me', (route) =>
      route.fulfill({ json: { id: 1, email: 'seller@example.com', is_seller: true } }),
    )
    await page.setViewportSize({ width, height: 800 })
    await page.goto('/my-listings')
    await settle(page)

    // Compare vertical CENTRES, not tops: the brand and the action group are
    // different heights, and in a centre-aligned flex row their tops legitimately
    // differ while they sit on the same line. Centres coincide on one row and
    // separate by roughly a row height when it wraps.
    const centres = await page.evaluate(() => {
      const bar = document.querySelector('header .MuiToolbar-root')
      if (!bar) return null
      return [...bar.children]
        .filter((el) => (el as HTMLElement).offsetParent !== null)
        .map((el) => {
          const r = el.getBoundingClientRect()
          return r.top + r.height / 2
        })
    })

    expect(centres, 'toolbar not found').not.toBeNull()
    const spread = Math.max(...centres!) - Math.min(...centres!)
    expect(
      spread,
      `nav children are ${spread.toFixed(1)}px apart vertically at ${width}px — it wrapped`,
    ).toBeLessThan(8)
  })
}

// DEFECT: the ring appeared twice — once inside the icon tile and once as the
// "O" of "Owner" — because the tile and the wordmark were shown together. They
// are alternatives, and this asserts exactly one is on screen.
for (const width of WIDTHS) {
  test(`exactly one brand lockup is visible @ ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 })
    await page.goto('/')
    await settle(page)

    const visible = await page
      .locator('header [aria-label="NextOwner"]:visible')
      .count()
    expect(visible, `${visible} brand lockups visible at ${width}px — expected exactly 1`).toBe(1)
  })
}

// DEFECT: the ring rendered ~1px above the baseline of the letters beside it,
// because it was centred in the line box rather than anchored to the baseline.
// Asserting the exact overshoot would be too tight to hold across platforms;
// asserting the ring is not *above* the cap is both robust and the thing that
// was actually wrong.
test('the ring sits on the text baseline, not above it', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/')
  await settle(page)

  const geometry = await page.evaluate(() => {
    const lockup = document.querySelector('header [aria-label="NextOwner"]')
    if (!lockup) return null
    const ring = lockup.querySelector('img')
    const text = [...lockup.querySelectorAll('span')].find((s) => s.textContent === 'wner')
    if (!ring || !text) return null
    return {
      ringBottom: ring.getBoundingClientRect().bottom,
      textBottom: text.getBoundingClientRect().bottom,
      ringHeight: ring.getBoundingClientRect().height,
    }
  })

  expect(geometry, 'wordmark ring or text not found').not.toBeNull()
  const { ringBottom, textBottom, ringHeight } = geometry!
  // A round glyph overshoots the baseline, so the ring's bottom should sit at
  // or below the text box's bottom — never above it, which is what the
  // line-box-centred version did.
  expect(
    ringBottom,
    `ring bottom (${ringBottom.toFixed(1)}) is above the text bottom (${textBottom.toFixed(1)})`,
  ).toBeGreaterThan(textBottom - ringHeight * 0.25)
})
