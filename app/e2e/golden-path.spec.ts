// M13 — spec 013, the E2E golden path (Phase D).
//
// One business, listed to sold, in a real browser against a real FastAPI and a
// real database. G1-G14 are steps of ONE test (spec 013 D1): the only thing
// this file can prove that the ~850 backend tests cannot is that state carries
// forward across all fourteen, and a test that re-seeds between them has thrown
// exactly that away. T1-T3 are separate tests — independent arrangements, no
// shared narrative.
//
// NOTHING IN THIS FILE MAY STUB A REQUEST. No `page.route`, no `fulfill`, no
// injected token. That is criterion X2, enforced by a scan in
// golden-path.guards.spec.ts, and it is the property that stops this suite
// proving that the frontend can render fixtures. Its neighbours here
// (screens/a11y/layout) stub everything, deliberately — do not copy them.
import { test, expect, type Browser, type Page } from '@playwright/test'

const PASSWORD = 'correct horse battery staple'

// One run, one empty database (spec 013 D7), so fixed addresses are safe. The
// reserved .test TLD (RFC 2606) keeps these unmailable if a later milestone
// adds a send. The admin is registered and then promoted by global setup —
// `make_admin` only ever promotes an existing row (spec 013 D6).
const SELLER = { email: 'seller@e2e.test', password: PASSWORD }
const BUYER = { email: 'buyer@e2e.test', password: PASSWORD }
const ADMIN = { email: 'admin@e2e.test', password: PASSWORD }

// D10 — the search term G6 uses. Unique enough that finding it is an assertion
// about *this* listing rather than about the marketplace being non-empty.
const HEADLINE = 'Profitable veterinary practice management SaaS'
const COMPANY = 'Willowbrook Veterinary Systems LLC'
const WEBSITE = 'https://willowbrook-vet.test'

// The private description — asserted PRESENT for the approved buyer (G10) and
// ABSENT for everyone else (G8). One constant, so the two halves cannot drift
// apart and quietly stop testing the same secret.
const PRIVATE_DETAIL = 'Net margin 34 percent after owner add-backs'
const OFFER_PRICE = '445000'

interface Listing {
  headline: string
  company: string
  website: string
  detail: string
}

// ── helpers ──────────────────────────────────────────────────────────────────

// Register goes through /register, which returns no token, so the real product
// then sends the visitor to /login. Both halves are walked here because that is
// what a human does — a helper that POSTed straight to /auth/login would skip
// the registration screen this milestone exists to cover.
async function registerAndLogIn(page: Page, who: { email: string; password: string }, role: 'buyer' | 'seller') {
  await page.goto('/register')
  await page.getByLabel('Email').fill(who.email)
  await page.getByLabel('Password').fill(who.password)
  await page.getByRole('radio', { name: new RegExp(`^${role}`, 'i') }).check()
  await page.getByRole('button', { name: 'Create account' }).click()
  await page.waitForURL('**/login')
  await logIn(page, who)
}

async function logIn(page: Page, who: { email: string; password: string }) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(who.email)
  await page.getByLabel('Password').fill(who.password)
  await page.getByRole('button', { name: /log in|sign in/i }).click()
  await expect(page.getByRole('button', { name: /log out|sign out/i })).toBeVisible()
}

// Fill and submit the wizard. Every metric is filled: `ListingCreate` requires
// all five, and a blank field serialises to "" which fails Decimal validation
// (spec 013 D12 — the guidance that said otherwise is corrected by F4).
async function createDraft(page: Page, listing: Listing) {
  await page.goto('/sell')

  await page.getByLabel('Headline').fill(listing.headline)
  await page.getByLabel('Asking price').fill('480000')
  await page.getByLabel('Business type').click()
  await page.getByRole('option', { name: /saas/i }).click()
  await page.getByRole('button', { name: 'Next' }).click()

  await page.getByLabel('TTM revenue').fill('320000')
  await page.getByLabel('TTM profit').fill('108000')
  await page.getByLabel('MRR').fill('27000')
  await page.getByLabel('Churn %').fill('1.80')
  await page.getByLabel('Customers').fill('412')
  await page.getByRole('button', { name: 'Next' }).click()

  await page.getByLabel('Company name').fill(listing.company)
  await page.getByLabel('Website URL').fill(listing.website)
  await page.getByLabel('Description').fill(listing.detail)
  await page.getByRole('button', { name: 'Next' }).click()

  await page.getByRole('button', { name: 'Create draft' }).click()
  await expect(page.getByText('Draft created.')).toBeVisible()
}

function cardFor(page: Page, headline: string) {
  return page.locator('.MuiCard-root').filter({ hasText: headline })
}

// Walk a listing all the way to `live` through the real product: seller
// registers, fills the wizard, submits for review, an admin approves. Used by
// the trust block, which needs a live listing of its own — the golden path
// ends with its listing SOLD, and a test that depended on another test's end
// state would be a different kind of test than this file claims to be.
async function publishListing(browser: Browser, seller: { email: string; password: string }, listing: Listing) {
  const sellerContext = await browser.newContext()
  const adminContext = await browser.newContext()
  try {
    const sellerPage = await sellerContext.newPage()
    await registerAndLogIn(sellerPage, seller, 'seller')
    await createDraft(sellerPage, listing)
    await sellerPage.goto('/my-listings')
    await cardFor(sellerPage, listing.headline).getByRole('button', { name: /submit for review/i }).click()
    await expect(cardFor(sellerPage, listing.headline).getByText('In review')).toBeVisible()

    const adminPage = await adminContext.newPage()
    await logIn(adminPage, ADMIN)
    await adminPage.goto('/admin')
    await cardFor(adminPage, listing.headline).getByRole('button', { name: 'Approve' }).click()
    await expect(cardFor(adminPage, listing.headline)).toHaveCount(0)
  } finally {
    await sellerContext.close()
    await adminContext.close()
  }
}

// Search browse for a headline and open its detail page; returns the listing id.
async function openFromBrowse(page: Page, headline: string): Promise<string> {
  await page.goto('/browse')
  await page.getByLabel('Search').fill(headline)
  await page.keyboard.press('Enter')
  const card = cardFor(page, headline)
  await expect(card).toBeVisible()
  await card.getByRole('link').first().click()
  await page.waitForURL(/\/browse\/\d+$/)
  return page.url().split('/').pop() as string
}

// ── the golden path ──────────────────────────────────────────────────────────

test('golden path: a business goes from listed to sold', async ({ browser }) => {
  // Two live sessions, not one that logs in and out (spec 013 D8). G11 needs
  // both open at once; the rest of the path is more honest for it.
  const sellerContext = await browser.newContext()
  const buyerContext = await browser.newContext()
  const adminContext = await browser.newContext()
  const sellerPage = await sellerContext.newPage()
  const buyerPage = await buyerContext.newPage()
  const adminPage = await adminContext.newPage()

  const listing: Listing = {
    headline: HEADLINE,
    company: COMPANY,
    website: WEBSITE,
    detail: PRIVATE_DETAIL,
  }
  let listingId = ''

  await test.step('G1: the seller registers and lands in the app', async () => {
    await registerAndLogIn(sellerPage, SELLER, 'seller')
    await sellerPage.goto('/my-listings')
    await expect(sellerPage).toHaveURL(/\/my-listings$/)
    await expect(sellerPage.getByRole('heading', { name: 'Your listings' })).toBeVisible()
  })

  await test.step('G2: the seller creates a listing through the wizard', async () => {
    await createDraft(sellerPage, listing)
    await sellerPage.goto('/my-listings')
    await expect(cardFor(sellerPage, HEADLINE).getByText('Draft')).toBeVisible()
  })

  await test.step('G3: the seller submits it for review', async () => {
    // The action spec 013 F1 adds. Before this milestone there was no caller of
    // POST /listings/{id}/submit anywhere in the frontend at all.
    await cardFor(sellerPage, HEADLINE).getByRole('button', { name: /submit for review/i }).click()
    await expect(cardFor(sellerPage, HEADLINE).getByText('In review')).toBeVisible()
    await expect(cardFor(sellerPage, HEADLINE).getByRole('button', { name: /submit for review/i })).toHaveCount(0)

    // Not public yet — curation is the only door to `live` (M3).
    await buyerPage.goto(`/browse?q=${encodeURIComponent(HEADLINE)}`)
    await expect(buyerPage.getByText(HEADLINE)).toHaveCount(0)
  })

  await test.step('G4: an admin approves it', async () => {
    await logIn(adminPage, ADMIN)
    await adminPage.goto('/admin')
    await expect(cardFor(adminPage, HEADLINE)).toBeVisible()
    await cardFor(adminPage, HEADLINE).getByRole('button', { name: 'Approve' }).click()
    await expect(cardFor(adminPage, HEADLINE)).toHaveCount(0)

    await sellerPage.reload()
    await expect(cardFor(sellerPage, HEADLINE).getByText('Live')).toBeVisible()
  })

  await test.step('G5: the buyer registers in an independent session', async () => {
    await registerAndLogIn(buyerPage, BUYER, 'buyer')
    await expect(buyerPage.getByRole('button', { name: /log out|sign out/i })).toBeVisible()
    // The seller's session is untouched — two humans, not one tab.
    await sellerPage.goto('/my-listings')
    await expect(sellerPage.getByRole('heading', { name: 'Your listings' })).toBeVisible()
  })

  await test.step('G6: the buyer finds it by search, and the card is anonymous', async () => {
    listingId = await openFromBrowse(buyerPage, HEADLINE)
    expect(listingId).toMatch(/^\d+$/)
    // FR-6: public means anonymous.
    const body = await buyerPage.locator('body').innerText()
    expect(body).not.toContain(COMPANY)
    expect(body).not.toContain(WEBSITE)
    expect(body).not.toContain(SELLER.email)
  })

  await test.step('G7: requesting access opens the NDA, which cannot be signed unread', async () => {
    await buyerPage.getByRole('button', { name: 'Request access' }).click()
    const modal = buyerPage.getByRole('dialog')
    await expect(modal).toBeVisible()
    // The click-wrap rule NdaModal's own comment calls load-bearing: a
    // signature that could be given without the affirmative act is not one.
    await expect(modal.getByRole('button', { name: 'Sign and request access' })).toBeDisabled()
  })

  await test.step('G8: signing the NDA files the request, and the gate stays shut', async () => {
    const modal = buyerPage.getByRole('dialog')
    await modal.getByRole('checkbox').check()
    await modal.getByRole('button', { name: 'Sign and request access' }).click()

    await expect(buyerPage.getByText('Access pending')).toBeVisible()
    const body = await buyerPage.locator('body').innerText()
    expect(body).not.toContain(COMPANY)
    expect(body).not.toContain(PRIVATE_DETAIL)
  })

  await test.step('G9: the seller approves the request', async () => {
    await sellerPage.goto(`/my-listings/${listingId}/requests`)
    const row = sellerPage.locator('.MuiCard-root').filter({ hasText: BUYER.email })
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: 'Approve' }).click()
    await expect(sellerPage.getByText(/approved/i).first()).toBeVisible()
  })

  await test.step('G10: the buyer now sees what the public card withheld', async () => {
    await buyerPage.reload()
    await expect(buyerPage.getByText(COMPANY)).toBeVisible()
    await expect(buyerPage.getByText(PRIVATE_DETAIL)).toBeVisible()
  })

  await test.step('G11: a chat message reaches the seller live', async () => {
    // Approving the request created the conversation (M6). Both parties open
    // it, and the assertion is delivery to the OTHER session with no reload —
    // which is why D8 insists on two contexts.
    await buyerPage.goto('/messages')
    await buyerPage.getByText(HEADLINE).first().click()
    await buyerPage.waitForURL(/\/messages\/\d+$/)
    const conversationPath = new URL(buyerPage.url()).pathname

    await sellerPage.goto(conversationPath)
    await expect(sellerPage.getByPlaceholder('Type a message')).toBeVisible()

    const question = 'Is the 1.8 percent churn figure net of annual contracts?'
    await buyerPage.getByPlaceholder('Type a message').fill(question)
    await buyerPage.getByRole('button', { name: 'Send' }).click()

    await expect(sellerPage.getByText(question)).toBeVisible()
  })

  await test.step('G12: the buyer submits an offer', async () => {
    await buyerPage.goto(`/browse/${listingId}`)
    await buyerPage.getByLabel('Price').fill(OFFER_PRICE)
    await buyerPage.getByLabel('Structure').fill('all cash')
    await buyerPage.getByLabel('Proposed close date').fill('2026-10-01')
    await buyerPage.getByRole('button', { name: /make an offer/i }).click()

    await buyerPage.goto('/my-offers')
    await expect(buyerPage.getByText(HEADLINE)).toBeVisible()
    await expect(buyerPage.getByText(/submitted|awaiting/i).first()).toBeVisible()
  })

  await test.step('G13: the seller accepts, and the listing goes under offer', async () => {
    await sellerPage.goto(`/my-listings/${listingId}/offers`)
    await sellerPage.getByRole('button', { name: 'Accept' }).click()
    await expect(sellerPage.getByText(/accepted/i).first()).toBeVisible()

    await sellerPage.goto('/my-listings')
    await expect(cardFor(sellerPage, HEADLINE).getByText('Under offer')).toBeVisible()
  })

  await test.step('G14: the seller marks it sold at the accepted price', async () => {
    await sellerPage.goto(`/my-listings/${listingId}/offers`)
    await sellerPage.getByRole('button', { name: 'Mark as sold' }).click()

    // The trigger and the confirm carry the same label, so the confirm must be
    // taken from inside the dialog rather than by name alone.
    const dialog = sellerPage.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: 'Mark as sold' }).click()

    await sellerPage.goto('/my-listings')
    await expect(cardFor(sellerPage, HEADLINE).getByText('Sold')).toBeVisible()
    // Server-derived from the accepted offer, never from a request body
    // (spec 012 D4). 445000 renders through formatPrice.
    await expect(cardFor(sellerPage, HEADLINE).getByText(/445,000/)).toBeVisible()

    // A sold listing leaves the marketplace (spec 012 D10 — browse is live-only).
    await buyerPage.goto(`/browse?q=${encodeURIComponent(HEADLINE)}`)
    await expect(buyerPage.getByText(HEADLINE)).toHaveCount(0)
  })

  await Promise.all([sellerContext.close(), buyerContext.close(), adminContext.close()])
})

// ── the trust checks ─────────────────────────────────────────────────────────
// These prove the BROWSER does not render what the API withheld. The backend
// suite proves the API withholds it; that is a different claim, and only one of
// the two can be made by a test that never opens a browser.
//
// They arrange their OWN live listing rather than reusing the golden path's,
// which ends `sold` and gone from the marketplace. Depending on another test's
// end state would also make these three unrunnable with `--grep T1`.

test.describe('trust checks in a real browser', () => {
  const GATED: Listing = {
    headline: 'Established dental billing platform for group practices',
    company: 'Northgate Billing Solutions Inc',
    website: 'https://northgate-billing.test',
    detail: 'Gross retention 96 percent across the top twenty accounts',
  }
  const GATED_SELLER = { email: 'gated-seller@e2e.test', password: PASSWORD }
  const OUTSIDER = { email: 'outsider@e2e.test', password: PASSWORD }

  test.beforeAll(async ({ browser }) => {
    await publishListing(browser, GATED_SELLER, GATED)
    // One outsider, registered once, used by T2 and T3 — so neither depends on
    // the other having run.
    const context = await browser.newContext()
    try {
      await registerAndLogIn(await context.newPage(), OUTSIDER, 'buyer')
    } finally {
      await context.close()
    }
  })

  test('T1: an anonymous visitor sees no identity on a live listing', async ({ page }) => {
    await openFromBrowse(page, GATED.headline)

    await expect(page.getByText(GATED.headline)).toBeVisible()
    const body = await page.locator('body').innerText()
    expect(body).not.toContain(GATED.company)
    expect(body).not.toContain(GATED.website)
    expect(body).not.toContain(GATED_SELLER.email)
    expect(body).not.toContain(GATED.detail)
  })

  test('T2: an authenticated buyer without approval sees the gate, not the financials', async ({ page }) => {
    await logIn(page, OUTSIDER)
    await openFromBrowse(page, GATED.headline)

    await expect(page.getByRole('button', { name: 'Request access' })).toBeVisible()
    const body = await page.locator('body').innerText()
    expect(body).not.toContain(GATED.company)
    expect(body).not.toContain(GATED.detail)
  })

  test('T3: a non-admin gets no curation queue', async ({ page }) => {
    await logIn(page, OUTSIDER)
    await page.goto('/admin')

    const body = await page.locator('body').innerText()
    expect(body).not.toContain(GATED.headline)
    await expect(page.getByRole('button', { name: 'Approve' })).toHaveCount(0)
  })
})
