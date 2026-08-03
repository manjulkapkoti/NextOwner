// M13 — spec 013, the guards that stop the golden path passing vacuously.
//
// Every other milestone's tests fail when the product breaks. This one could
// keep passing — against stubs, against a stale server, against a database left
// over from the previous run. These two criteria are what make a green golden
// path mean something.
//
// This file DOES stub, which is exactly why it is not golden-path.spec.ts: X2
// forbids the idiom there, and a scan with an exception encoded in it is a scan
// that will eventually be argued with.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { test, expect } from '@playwright/test'

const HERE = dirname(fileURLToPath(import.meta.url))
const GOLDEN = join(HERE, 'golden-path.spec.ts')

test('X1: a failing backend fails the run rather than passing it', async ({ page }) => {
  // Force the auth surface to fail, then walk G1's opening move. If the app
  // could reach an authenticated dashboard without a successful response, G1's
  // assertion would be measuring the frontend's optimism rather than the
  // product working — and the whole golden path would be built on it.
  await page.route('**/api/auth/**', (route) =>
    route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"forced"}' }),
  )

  await page.goto('/register')
  await page.getByLabel('Email').fill('vacuity@e2e.test')
  await page.getByLabel('Password').fill('correct horse battery staple')
  await page.getByRole('button', { name: 'Create account' }).click()

  // The two things that must NOT happen: a silent success, or a session.
  //
  // The session check reads the ACCOUNT MENU, which is what an authenticated
  // nav actually renders. It was written against a log-out button, and that
  // assertion could never have failed: logout lives inside this menu, so no
  // button by that name exists on any page, signed in or out. A guard against
  // vacuity that was itself vacuous — found while running the path.
  await expect(page).not.toHaveURL(/\/my-listings/)
  await expect(page.getByRole('button', { name: 'Account menu' })).toHaveCount(0)
  await expect(page.getByRole('alert')).toBeVisible()
})

test('X2: the golden path never intercepts a request', async () => {
  const source = readFileSync(GOLDEN, 'utf8')

  // Strip line comments before scanning: the file's own header explains the
  // rule and names the forbidden calls, and a scan that trips over the
  // documentation of the rule it enforces is a scan nobody will keep.
  const code = source
    .split('\n')
    .filter((line) => !line.trimStart().startsWith('//'))
    .join('\n')

  const forbidden: Array<[string, RegExp]> = [
    ['page.route (request interception)', /\.route\s*\(/],
    ['route.fulfill (a synthesised response)', /\.fulfill\s*\(/],
    ['a pre-injected auth token', /localStorage\.setItem/],
    ['addInitScript (the usual way a token is injected)', /addInitScript\s*\(/],
  ]

  for (const [what, pattern] of forbidden) {
    expect(pattern.test(code), `golden-path.spec.ts must not use ${what}`).toBe(false)
  }
})
