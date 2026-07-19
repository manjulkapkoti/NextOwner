// The business-type vocabulary, in one place.
//
// The wire value is a lowercase slug (`saas`) because that is what the API
// filters on; the display label is title-cased (`SaaS`) because that is what a
// person reads. Keeping both here stops the two drifting: the browse filter
// showed "SaaS" in its dropdown while the cards beside it showed "saas".
export const LISTING_TYPES = [
  { value: 'saas', label: 'SaaS' },
  { value: 'ecommerce', label: 'Ecommerce' },
  { value: 'content', label: 'Content' },
  { value: 'agency', label: 'Agency' },
  { value: 'marketplace', label: 'Marketplace' },
] as const

/** Display label for a wire value, falling back to the value itself.
 *
 * The fallback matters: `listing.type` is a free-text column, so a value this
 * list doesn't know about must still render as something rather than vanish.
 */
export function listingTypeLabel(value: string): string {
  return LISTING_TYPES.find((entry) => entry.value === value)?.label ?? value
}
