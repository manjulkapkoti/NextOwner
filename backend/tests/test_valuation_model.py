"""M11 — the valuation model itself (V1-V13), spec 011 §6.

Written failing first (constitution Article 3 §2). **Nothing this file imports
exists yet**: `app.valuation`, `estimate_valuation`, and the band tables are all
unwritten, so every test here fails at import with `ModuleNotFoundError`. That is
the correct red phase — it proves the tests reach for the real module rather than
a mock of it (the pre-011 rule, restated).

This is the milestone's only pure-unit file: no client, no session, no fixtures.
That is the point of D1 putting the model in its own module — `testing_guide.md`
§5's M11 checklist asks for exactly one thing, *"a unit table-test … (type,
revenue, profit, churn) → expected range, incl. edge cases"*, and V1 is it.

**Every expected number below comes from spec §6.6, not from running the code.**
If an implementation disagrees with this table, the implementation is wrong until
the spec is deliberately amended — that is the whole reason §6 is normative.

The three properties asserted around the table (V6-V8 monotonicity, V11 shape,
V12 determinism) matter more than the constants: the constants are business
policy someone will re-tune, and these three must survive the re-tuning.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.valuation import estimate_valuation


def _est(
    *,
    type="saas",
    ttm_revenue="200000",
    ttm_profit="100000",
    growth_pct="0",
    churn_pct="0",
):
    """Call the model with Decimal inputs and spec-§6.6 defaults.

    Defaults are row 1 of the table, so every test that varies one input is
    varying it against a case whose expected value is already pinned by V1.
    """
    return estimate_valuation(
        type=type,
        ttm_revenue=Decimal(ttm_revenue),
        ttm_profit=Decimal(ttm_profit),
        growth_pct=Decimal(growth_pct),
        churn_pct=Decimal(churn_pct),
    )


# Spec §6.6, transcribed verbatim. Order: type, revenue, profit, growth, churn,
# driver, low, high.
SPEC_TABLE = [
    ("saas", "200000", "100000", "0", "0", "profit", "300000", "500000"),
    ("saas", "200000", "100000", "100", "0", "profit", "450000", "750000"),
    ("saas", "200000", "100000", "0", "20", "profit", "150000", "250000"),
    ("saas", "200000", "0", "0", "0", "revenue", "400000", "800000"),
    ("saas", "200000", "-50000", "0", "0", "revenue", "400000", "800000"),
    ("agency", "200000", "100000", "0", "0", "profit", "150000", "250000"),
    ("ecommerce", "200000", "100000", "0", "0", "profit", "200000", "350000"),
    ("content", "200000", "100000", "0", "0", "profit", "250000", "400000"),
    ("marketplace", "200000", "100000", "0", "0", "profit", "300000", "500000"),
    ("saas", "0", "0", "0", "0", "none", "0", "0"),
    ("saas", "200000", "100000", "900", "95", "profit", "225000", "375000"),
    ("saas", "200000", "100000", "100", "20", "profit", "225000", "375000"),
]


@pytest.mark.parametrize(
    "type,revenue,profit,growth,churn,driver,low,high",
    SPEC_TABLE,
    ids=[f"row{i + 1}" for i in range(len(SPEC_TABLE))],
)
def test_v1_spec_table(type, revenue, profit, growth, churn, driver, low, high):
    """V1 — every representative case in spec §6.6 computes to its stated range.

    The checklist's one ☐. Rows 11 and 12 are the pair that proves the clamps do
    the work: 11 feeds absurd growth (900) and absurd churn (95), 12 feeds the
    largest *valid* values of each (100 / 20), and both must land on the same
    combined factor of 0.75. If clamping were missing, row 11 would explode and
    row 12 would still pass — which is why neither row alone is sufficient.
    """
    result = _est(
        type=type,
        ttm_revenue=revenue,
        ttm_profit=profit,
        growth_pct=growth,
        churn_pct=churn,
    )
    assert result.driver == driver
    assert result.low == Decimal(low)
    assert result.high == Decimal(high)


def test_v2_profitable_uses_profit_driver():
    """V2 — a profitable business is valued on profit, not revenue."""
    result = _est(ttm_revenue="1000000", ttm_profit="100000")
    assert result.driver == "profit"
    # Profit-driven: 100k x the saas profit band (3.0-5.0), NOT 1M x anything.
    # Asserting the value (not just the driver label) is what makes this test
    # about the arithmetic rather than about a string.
    assert result.low == Decimal("300000")
    assert result.high == Decimal("500000")


def test_v3_zero_profit_uses_revenue_driver():
    """V3 — the checklist's "zero profit" edge case.

    Zero is the boundary of §6.3's `ttm_profit > 0` test, so this is the case a
    `>=` typo would silently break: it would return a profit-driven 0-0 range and
    tell a visitor their business is worth nothing.
    """
    result = _est(ttm_revenue="200000", ttm_profit="0")
    assert result.driver == "revenue"
    assert result.low == Decimal("400000")
    assert result.high == Decimal("800000")


def test_v4_loss_making_uses_revenue_and_never_goes_negative():
    """V4 — a loss-making business is valued on revenue, and the range stays >= 0.

    The failure this guards is the obvious one: multiplying a negative profit by
    a positive band gives a negative "valuation", which is both nonsense and a
    number this page would happily render to a stranger.
    """
    result = _est(ttm_revenue="200000", ttm_profit="-90000")
    assert result.driver == "revenue"
    assert result.low >= 0
    assert result.low == Decimal("400000")
    assert result.high == Decimal("800000")


def test_v5_no_signal_returns_zero_range_not_an_error():
    """V5 — both figures zero is valid input that yields no estimate.

    Deliberately a 0-0 result with `driver == "none"`, not an exception: the
    inputs are well-formed, so rejecting them would push a modelling outcome into
    the validation layer, and the route would 422 on a form somebody filled in
    correctly (they just have no revenue yet).
    """
    result = _est(ttm_revenue="0", ttm_profit="0")
    assert result.driver == "none"
    assert result.low == Decimal("0")
    assert result.high == Decimal("0")
    assert result.explanation  # a friendly sentence, not an empty string


def test_v6_monotonic_in_profit():
    """V6 — more profit never lowers the estimate (spec D5)."""
    lower = _est(ttm_revenue="500000", ttm_profit="100000")
    higher = _est(ttm_revenue="500000", ttm_profit="200000")
    assert higher.low >= lower.low
    assert higher.high >= lower.high


def test_v7_monotonic_in_churn():
    """V7 — more churn never raises the estimate (spec D5)."""
    lower = _est(churn_pct="2")
    higher = _est(churn_pct="15")
    assert higher.low <= lower.low
    assert higher.high <= lower.high


def test_v8_monotonic_in_growth():
    """V8 — more growth never lowers the estimate (spec D5)."""
    lower = _est(growth_pct="0")
    higher = _est(growth_pct="60")
    assert higher.low >= lower.low
    assert higher.high >= lower.high


def test_v9_absurd_churn_is_clamped_not_extrapolated():
    """V9 — the checklist's "absurd churn" edge case.

    95% monthly churn is a real number a visitor can type. Extrapolated, §6.4's
    `1 - churn/40` would give `-1.375` — a *negative* multiple, and a negative
    valuation on a public page. Clamped at 20, the factor floors at 0.50.
    """
    result = _est(churn_pct="95")
    assert result.low >= 0
    # Identical to churn=20, the clamp boundary (spec row 3).
    assert result.low == Decimal("150000")
    assert result.high == Decimal("250000")


def test_v10_absurd_growth_is_clamped_not_extrapolated():
    """V10 — extreme claimed growth cannot inflate the estimate without bound.

    Someone will type 900. Unclamped, §6.4's `1 + growth/200` would be 5.5x, and
    the tool would report a number it has no basis for from one optimistic input.
    Clamped at 100, the factor caps at 1.50 — identical to spec row 2.
    """
    result = _est(growth_pct="900")
    assert result.low == Decimal("450000")
    assert result.high == Decimal("750000")


@pytest.mark.parametrize(
    "type,revenue,profit,growth,churn",
    [(row[0], row[1], row[2], row[3], row[4]) for row in SPEC_TABLE],
    ids=[f"row{i + 1}" for i in range(len(SPEC_TABLE))],
)
def test_v11_result_is_ordered_whole_decimals(type, revenue, profit, growth, churn):
    """V11 — `low <= high`, both exact `Decimal`, both whole units (D6, §6.5).

    Run over every spec row rather than one case, because the float-artifact
    failure mode is input-dependent: a `float` implementation passes on round
    numbers and produces `.30000000000000004` on the awkward ones.
    """
    result = _est(
        type=type,
        ttm_revenue=revenue,
        ttm_profit=profit,
        growth_pct=growth,
        churn_pct=churn,
    )
    assert isinstance(result.low, Decimal)
    assert isinstance(result.high, Decimal)
    assert result.low <= result.high
    assert result.low == result.low.to_integral_value()
    assert result.high == result.high.to_integral_value()


def test_v12_deterministic():
    """V12 — same inputs, same output. No clock, no randomness (D5).

    Cheap to assert and worth asserting: the moment somebody "improves" this with
    a jitter or a date-based adjustment, the lead row stops matching the number
    the visitor was shown.
    """
    first = _est(growth_pct="35", churn_pct="7")
    second = _est(growth_pct="35", churn_pct="7")
    assert (first.low, first.high, first.driver) == (second.low, second.high, second.driver)


def test_v13_each_type_uses_its_own_band():
    """V13 — the lookup is keyed on type, never defaulted (D12).

    Holding every other input equal, the five types must produce five results
    that are not all identical, and each must match its own §6.2 band. A
    `.get(type, SAAS_BAND)` implementation passes a single-type test and fails
    this one.
    """
    expected = {
        "saas": (Decimal("300000"), Decimal("500000")),
        "marketplace": (Decimal("300000"), Decimal("500000")),
        "content": (Decimal("250000"), Decimal("400000")),
        "ecommerce": (Decimal("200000"), Decimal("350000")),
        "agency": (Decimal("150000"), Decimal("250000")),
    }
    for business_type, (low, high) in expected.items():
        result = _est(type=business_type)
        assert (result.low, result.high) == (low, high), business_type

    # ...and the set is genuinely differentiated, not five aliases of one band.
    assert len({(low, high) for low, high in expected.values()}) == 4
