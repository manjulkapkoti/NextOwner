"""The valuation calculator — the public front door (M11, FR-23, spec 011).

The inverse of every router since M1. There is no owner here, no counterparty and
no state machine: both routes are anonymous by design, and neither reads the
caller's identity at all. So the questions this file has to answer are not
"may this caller see this row?" but:

- **can an anonymous caller make us store something we shouldn't?** — the lead
  route recomputes the estimate server-side and never reads one from the body,
  and its limiter is enforced *before* the insert so the table is actually
  bounded (spec S5, S11);
- **can an anonymous caller make us say something we shouldn't?** — the request
  models carry only the five inputs, `type` is a closed whitelist, and the
  response model is standalone with no path to another table (S4, S6, S8).

**Two routes, not one with an optional `email`** (spec D2). That split is the
security design: the route that everyone hits stores nothing, so the anonymous
traffic surface can never become a PII-collection or storage-exhaustion surface.
A combined route would put the write path one JSON field away from every request.

**A token present must change nothing** (S9). This module never depends on
`get_current_user`, mirroring `browse_listings`' "no widening if a token is
present" — and here it also means a lead captured by a signed-in visitor does not
silently become an identified lead, which is the linkage `ValuationLead`'s
missing `user_id` FK exists to prevent (D10).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from ..config import settings
from ..db import get_session
from ..models import ValuationLead
from ..ratelimit import RateLimiter, enforce_per_ip
from ..schemas import ValuationEstimateRead, ValuationLeadCreate, ValuationRequest
from ..valuation import DISCLAIMER, Estimate, estimate_valuation

router = APIRouter(tags=["valuation"])

# Two limiters, two very different caps (D8). Named so `key_for` namespaces their
# counters apart — sharing one would let ordinary calculator use exhaust the lead
# budget, and a lead-form abuser lock real visitors out of the calculator.
_valuation_limiter = RateLimiter(
    max_attempts=settings.valuation_rate_limit_max,
    window_seconds=settings.valuation_rate_limit_window_seconds,
    name="valuation",
)
_valuation_lead_limiter = RateLimiter(
    max_attempts=settings.valuation_lead_rate_limit_max,
    window_seconds=settings.valuation_lead_rate_limit_window_seconds,
    name="valuation_lead",
)


def _to_read(estimate: Estimate) -> ValuationEstimateRead:
    """The one place an `Estimate` becomes a response, so the disclaimer cannot
    be forgotten on one route and remembered on the other (D11)."""
    return ValuationEstimateRead(
        low=estimate.low,
        high=estimate.high,
        driver=estimate.driver,
        explanation=estimate.explanation,
        disclaimer=DISCLAIMER,
    )


@router.post("/valuation", response_model=ValuationEstimateRead)
def calculate_valuation(body: ValuationRequest, request: Request) -> ValuationEstimateRead:
    """Public, anonymous, and **writes nothing** (spec C1-C5).

    No session dependency at all — not as an optimization, but so that "this
    route persists nothing" is visible in the signature rather than being a
    property of the body that someone has to keep true.
    """
    # Before any work — a refused request must cost nothing (pre-011 R1).
    enforce_per_ip(_valuation_limiter, request)

    return _to_read(
        estimate_valuation(
            type=body.type,
            ttm_revenue=body.ttm_revenue,
            ttm_profit=body.ttm_profit,
            growth_pct=body.growth_pct,
            churn_pct=body.churn_pct,
        )
    )


@router.post("/valuation/leads", response_model=ValuationEstimateRead, status_code=201)
def capture_valuation_lead(
    body: ValuationLeadCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> ValuationEstimateRead:
    """FR-23's second half: the estimate, plus the address, on the record.

    Three properties worth stating because each is a test:

    - **The limiter runs before the insert** (S11). A cap checked after the write
      still returns 429 and still leaves the row behind, which bounds nothing —
      and bounding this table is the entire reason the cap is 5/hour rather than
      the calculate route's 30/minute.
    - **The stored estimate is ours** (L2/S5). `ValuationLeadCreate` has no
      `low`/`high` fields to read even if we wanted to, so the recomputation
      below is the only possible source.
    - **The response is identical for a first-time and a repeat address** (D7).
      No unique constraint and no 409: a duplicate-detecting error would answer
      "is this address already known to NextOwner?" for anyone who asked.

    The address is never logged (D10); it leaves this process only through the
    `require_admin` route in `routers/admin.py`.
    """
    enforce_per_ip(_valuation_lead_limiter, request)

    estimate = estimate_valuation(
        type=body.type,
        ttm_revenue=body.ttm_revenue,
        ttm_profit=body.ttm_profit,
        growth_pct=body.growth_pct,
        churn_pct=body.churn_pct,
    )

    session.add(
        ValuationLead(
            email=body.email,
            type=body.type,
            ttm_revenue=body.ttm_revenue,
            ttm_profit=body.ttm_profit,
            growth_pct=body.growth_pct,
            churn_pct=body.churn_pct,
            estimate_low=estimate.low,
            estimate_high=estimate.high,
            driver=estimate.driver,
        )
    )
    session.commit()

    return _to_read(estimate)
