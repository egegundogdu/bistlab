import datetime as dt
import math

import pandas as pd
import pytest
from sqlalchemy.orm import Session

from bistlab.data.db import get_engine, init_db
from bistlab.data.financials import save_financials
from bistlab.valuation.ratios import compute_ratios
from bistlab.valuation.report import load_items

Y1 = dt.date(2024, 12, 31)
Y2 = dt.date(2025, 12, 31)


def _items() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Total Revenue": [100.0, 120.0],
            "Gross Profit": [30.0, 42.0],
            "EBITDA": [20.0, 30.0],
            "EBIT": [15.0, 24.0],
            "Interest Expense": [5.0, 0.0],
            "Net Income": [10.0, 12.0],
            "Common Stock Equity": [50.0, 60.0],
            "Current Assets": [40.0, 45.0],
            "Current Liabilities": [20.0, 30.0],
            "Total Debt": [70.0, 80.0],
            "Cash And Cash Equivalents": [10.0, 20.0],
        },
        index=[Y1, Y2],
    )


def test_compute_ratios_values() -> None:
    r = compute_ratios(_items()).loc[Y2]
    assert r["revenue_growth"] == pytest.approx(0.20)
    assert r["gross_margin"] == pytest.approx(0.35)
    assert r["ebitda_margin"] == pytest.approx(0.25)
    assert r["net_margin"] == pytest.approx(0.10)
    assert r["roe"] == pytest.approx(0.20)
    assert r["current_ratio"] == pytest.approx(1.5)
    assert r["net_debt_to_ebitda"] == pytest.approx(2.0)


def test_zero_division_and_missing_items_become_nan() -> None:
    r = compute_ratios(_items().drop(columns=["Gross Profit"])).loc[Y2]
    assert math.isnan(r["interest_coverage"])
    assert math.isnan(r["gross_margin"])


def test_load_items_returns_wide_table_and_currency() -> None:
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    rows = [(Y2, "income", "Total Revenue", 120.0), (Y2, "income", "EBITDA", 30.0)]
    with Session(engine) as session:
        save_financials(session, "TEST", rows, "USD")
        wide, currency = load_items(session, "TEST")
    assert currency == "USD"
    assert wide.loc[Y2, "EBITDA"] == 30.0
