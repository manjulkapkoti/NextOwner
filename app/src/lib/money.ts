// Money formatting for display. Its own module, not a named export beside a
// component: `react-refresh/only-export-components` (error-level in CI, which
// runs `eslint --max-warnings 0`) rejects a file that exports both a component
// and a helper, and a shared formatter is exactly the thing two screens want.
//
// The API sends money as an **exact decimal string** (the `Money` type keeps
// `Decimal` lossless end to end — never float). Parsing to `number` here is for
// rendering only; nothing computed from this value is ever sent back.

export function formatPrice(value: string | null | undefined): string | null {
  if (value === null || value === undefined || value === '') return null
  const amount = Number(value)
  // Fall back to the raw string rather than rendering `NaN`: a value this
  // cannot parse is a reason to show it verbatim, not to invent one.
  if (!Number.isFinite(amount)) return value
  return amount.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  })
}
