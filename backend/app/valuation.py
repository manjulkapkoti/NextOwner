"""The valuation model — a rule of thumb, in one place (M11, spec 011 §6).

Pure by construction: no session, no request, no clock, no randomness. That is
what lets `test_valuation_model.py` be a table test with no fixtures, and what
makes spec §6 checkable against this file line by line.

**Why this is a module and not a helper inside the router** (spec D1): the bands
below are *published business policy* (FR-23's words), and FR-23 also says the
estimate is captured onto a lead row. Two callers, one rule — so the rule gets
one home. The alternative the build guide offered, computing this in the browser,
was declined for the same reason plus a third: a TypeScript copy and a Python
copy of a pricing table drift the week after they ship.

**Everything is `Decimal`, including the multipliers.** Not defensive habit —
`float` on this path produces `.30000000000000004` on a marketing page, and the
same number is persisted onto the lead row an admin later quotes back.

The constants are policy and will be re-tuned. The three properties the tests pin
around them are not: the model is **deterministic**, **total** (every input that
passes validation produces an answer — nothing here raises), and **monotonic** —
more profit or growth never lowers the estimate, more churn never raises it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

ValuationType = Literal["saas", "ecommerce", "content", "agency", "marketplace"]

#: The whitelist, in one place so the schema and the bands cannot disagree.
VALUATION_TYPES: tuple[str, ...] = ("saas", "ecommerce", "content", "agency", "marketplace")

Driver = Literal["profit", "revenue", "none"]

# ── Bands (spec §6.2) ────────────────────────────────────────────────────────
#
# Keyed on type with **no default** (spec D12). A `.get(type, SAAS)` fallback
# would attach a SaaS multiple to anything unrecognized — a wrong answer
# delivered with full confidence, which on this surface is worse than an error.
# The schema rejects an unknown type before we get here; `_band` raises if that
# ever stops being true, rather than guessing.

PROFIT_BANDS: dict[str, tuple[Decimal, Decimal]] = {
    "saas": (Decimal("3.0"), Decimal("5.0")),
    "marketplace": (Decimal("3.0"), Decimal("5.0")),
    "content": (Decimal("2.5"), Decimal("4.0")),
    "ecommerce": (Decimal("2.0"), Decimal("3.5")),
    "agency": (Decimal("1.5"), Decimal("2.5")),
}

REVENUE_BANDS: dict[str, tuple[Decimal, Decimal]] = {
    "saas": (Decimal("2.0"), Decimal("4.0")),
    "marketplace": (Decimal("2.0"), Decimal("4.0")),
    "content": (Decimal("1.5"), Decimal("3.0")),
    "ecommerce": (Decimal("0.6"), Decimal("1.2")),
    "agency": (Decimal("0.5"), Decimal("1.0")),
}

# ── Adjustment bounds (spec §6.4) ────────────────────────────────────────────
#
# The inner clamps are the whole safety story here. Someone *will* type 900%
# growth and 95% churn — both are things a person can believe about their own
# business. Extrapolated, the churn term goes negative (`1 - 95/40 = -1.375`) and
# the tool reports a negative valuation; the growth term reaches 5.5x and the
# tool reports a number it has no basis for. Clamping means an absurd input is
# ignored past the band edge rather than trusted and multiplied out.

_GROWTH_FLOOR, _GROWTH_CEILING = Decimal("-50"), Decimal("100")
_GROWTH_DIVISOR = Decimal("200")

_CHURN_FLOOR, _CHURN_CEILING = Decimal("0"), Decimal("20")
_CHURN_DIVISOR = Decimal("40")

_COMBINED_FLOOR, _COMBINED_CEILING = Decimal("0.50"), Decimal("1.75")

#: Fixed, server-owned, and part of the API response rather than UI chrome
#: (spec D11). `agentic_scope.md` § Liability: a valuation output is decision
#: support, not advice — and a client that renders the number while dropping the
#: caveat is a client bug we can prevent by never separating them.
DISCLAIMER = (
    "This is a rough estimate based on published rules of thumb, not a valuation "
    "or financial advice. Real offers depend on diligence, growth quality, "
    "customer concentration, and how transferable the business is."
)

_TYPE_LABELS = {
    "saas": "SaaS",
    "ecommerce": "ecommerce",
    "content": "content",
    "agency": "agency",
    "marketplace": "marketplace",
}


@dataclass(frozen=True)
class Estimate:
    """What the model returns. Frozen — nothing downstream adjusts an estimate
    after the fact; a different answer means different inputs."""

    low: Decimal
    high: Decimal
    driver: Driver
    explanation: str


def _clamp(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    return max(low, min(high, value))


def _band(type: str, driver: Driver) -> tuple[Decimal, Decimal]:
    bands = PROFIT_BANDS if driver == "profit" else REVENUE_BANDS
    try:
        return bands[type]
    except KeyError:  # pragma: no cover - the schema whitelist gets here first
        raise ValueError(f"no valuation band for type {type!r}") from None


def _round_to_unit(value: Decimal) -> Decimal:
    """Whole currency units, ROUND_HALF_UP (spec §6.5).

    Half-up rather than banker's rounding because this number is read by a
    person, and "why is 2.5 sometimes 2 and sometimes 3" is a support question
    nobody should have to answer about a marketing page.
    """
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def estimate_valuation(
    *,
    type: str,
    ttm_revenue: Decimal,
    ttm_profit: Decimal,
    growth_pct: Decimal = Decimal("0"),
    churn_pct: Decimal = Decimal("0"),
) -> Estimate:
    """Spec §6, end to end: driver → band → factors → clamp → round.

    Keyword-only: five numeric-ish arguments in a row is exactly the signature
    where a positional swap (revenue for profit) produces a plausible wrong
    answer instead of an error.
    """
    # ── Driver (§6.3) ────────────────────────────────────────────────────────
    # `> 0`, not `>= 0`: a business at exactly break-even has no profit to apply
    # a multiple to, and a profit-driven zero would tell its owner the business
    # is worth nothing. Revenue is the honest basis there.
    if ttm_profit > 0:
        driver: Driver = "profit"
        base = ttm_profit
    elif ttm_revenue > 0:
        driver = "revenue"
        base = ttm_revenue
    else:
        return Estimate(
            low=Decimal("0"),
            high=Decimal("0"),
            driver="none",
            explanation=(
                "With no trailing revenue or profit yet, there is nothing to apply a "
                "multiple to. Come back once the business has a full year of trading "
                "behind it — or list it anyway and let buyers price the assets."
            ),
        )

    band_low, band_high = _band(type, driver)

    # ── Factors (§6.4) ───────────────────────────────────────────────────────
    growth_factor = 1 + _clamp(growth_pct, _GROWTH_FLOOR, _GROWTH_CEILING) / _GROWTH_DIVISOR
    churn_factor = 1 - _clamp(churn_pct, _CHURN_FLOOR, _CHURN_CEILING) / _CHURN_DIVISOR
    combined = _clamp(growth_factor * churn_factor, _COMBINED_FLOOR, _COMBINED_CEILING)

    low = _round_to_unit(base * band_low * combined)
    high = _round_to_unit(base * band_high * combined)

    return Estimate(
        low=low,
        high=high,
        driver=driver,
        explanation=_explain(
            type=type,
            driver=driver,
            band_low=band_low,
            band_high=band_high,
            growth_factor=growth_factor,
            churn_factor=churn_factor,
        ),
    )


def _explain(
    *,
    type: str,
    driver: Driver,
    band_low: Decimal,
    band_high: Decimal,
    growth_factor: Decimal,
    churn_factor: Decimal,
) -> str:
    """The "friendly explanation" Part 4 asks for.

    Names the driver and the band always, and each adjustment only when it moved
    the number — a sentence listing factors of 1.0 reads like an apology for
    doing nothing, and buries the ones that mattered.
    """
    basis = "profit" if driver == "profit" else "revenue"
    label = _TYPE_LABELS.get(type, type)
    sentence = (
        f"{label} businesses typically trade at "
        f"{_plain(band_low)}–{_plain(band_high)}× trailing-twelve-month {basis}, "
        f"so that is the starting range."
    )

    adjustments = []
    if growth_factor > 1:
        adjustments.append("growth pushed it up")
    elif growth_factor < 1:
        adjustments.append("the revenue decline pulled it down")
    if churn_factor < 1:
        adjustments.append("churn pulled it down")

    if adjustments:
        sentence += " From there, " + " and ".join(adjustments) + "."
    return sentence


def _plain(value: Decimal) -> str:
    """`3.0` → "3", `3.5` → "3.5" — a multiple a person would say out loud."""
    return str(value.normalize())
