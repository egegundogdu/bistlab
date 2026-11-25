import math

import pandas as pd
import pytest

from bistlab.credit.scores import (
    altman_z_em,
    altman_zone,
    credit_table,
    interest_coverage,
    synthetic_rating,
)


def test_altman_z_em_formula() -> None:
    # X1=0,2  X2=0,3  X3=0,1  X4=1,5
    z = altman_z_em(20, 30, 10, 100, 60, 40)
    expected = 3.25 + 6.56 * 0.2 + 3.26 * 0.3 + 6.72 * 0.1 + 1.05 * 1.5
    assert z == pytest.approx(expected)


def test_altman_zone() -> None:
    assert altman_zone(7.0) == "güvenli"
    assert altman_zone(5.0) == "gri"
    assert altman_zone(3.0) == "sıkıntı"


def test_interest_coverage_handles_sign_and_zero() -> None:
    assert interest_coverage(100, -25) == pytest.approx(4.0)
    assert math.isinf(interest_coverage(100, 0))


@pytest.mark.parametrize(
    ("coverage", "rating"),
    [(math.inf, "AAA"), (8.5, "AAA"), (2.6, "BBB"), (1.3, "B-"), (0.1, "D"), (-3.0, "D")],
)
def test_synthetic_rating(coverage: float, rating: str) -> None:
    assert synthetic_rating(coverage)[0] == rating


def test_credit_table_uses_current_items_when_working_capital_missing() -> None:
    items = pd.DataFrame(
        {
            "Current Assets": [50.0],
            "Current Liabilities": [30.0],
            "Retained Earnings": [30.0],
            "EBIT": [10.0],
            "Total Assets": [100.0],
            "Stockholders Equity": [60.0],
            "Total Liabilities Net Minority Interest": [40.0],
            "Interest Expense": [2.0],
        },
        index=["2025-12-31"],
    )
    table = credit_table(items)
    row = table.iloc[0]
    assert row["z"] == pytest.approx(altman_z_em(20, 30, 10, 100, 60, 40))
    assert row["coverage"] == pytest.approx(5.0)
    assert row["rating"] == "A"


def test_credit_table_skips_incomplete_periods() -> None:
    items = pd.DataFrame({"EBIT": [10.0]}, index=["2025-12-31"])
    assert credit_table(items).empty
