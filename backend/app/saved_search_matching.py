"""Does this listing match a saved search? (M8, FR-11)

The mirror of `browse_listings`' WHERE clause, evaluated in Python against one
listing instead of in SQL against the table. Two reasons it is a mirror rather
than a reuse of the query itself:

- the fan-out asks the **inverse** question ("which of N searches match this
  one listing?"), and running N SQL queries at publication to answer it would
  put a table scan per subscriber on the critical path of an admin's approve;
- comparing `Decimal` to `Decimal` in Python is exact, which sidesteps the
  `Money`-as-TEXT trap M4 had to cast around (`'90000.00' > '200000.00'` is
  true as strings). No cast, no lexicographic surprise.

**The predicates must stay in step with `browse_listings`.** A filter that
matches here but not there — or vice versa — means an alert that leads to a
listing the buyer cannot find, or a listing that never alerts. The strict
`SavedSearchFilters` schema is what keeps the *field set* honest; this module
keeps the *semantics* honest, and spec B1/B2 are the tests that notice.
"""

from __future__ import annotations

import json

from .models import Listing
from .schemas import SavedSearchFilters


def parse_filters(filters_json: str) -> SavedSearchFilters:
    """Re-validate a stored blob through the same schema that accepted it.

    Validating on the way **out** as well as in is deliberate: the row could
    have been written by an older schema version, and a filter set that no
    longer validates must fail loudly here rather than silently matching
    everything (which is what a bare `json.loads` into a dict would do).
    """
    return SavedSearchFilters.model_validate(json.loads(filters_json))


def listing_matches(listing: Listing, filters: SavedSearchFilters) -> bool:
    """True when this listing satisfies every set filter.

    Unset filters do not constrain — an empty saved search matches everything,
    which is the same thing an unfiltered browse does.
    """
    # Truthiness, not `is not None`, mirroring `browse_listings`: an empty
    # `type` is how a cleared dropdown serializes and must mean "no filter"
    # rather than "match the empty string".
    if filters.type and listing.type != filters.type:
        return False
    if filters.min_price is not None and listing.asking_price < filters.min_price:
        return False
    if filters.max_price is not None and listing.asking_price > filters.max_price:
        return False
    if filters.min_profit is not None and listing.ttm_profit < filters.min_profit:
        return False
    if filters.q:
        term = filters.q.casefold()
        haystack = f"{listing.headline}\n{listing.description}".casefold()
        if term not in haystack:
            return False
    return True
