import datetime as dt
import math

import pandas as pd
import pytest

from bistlab.valuation.multiples import compute_multiples

YEAR_END = dt.date(2025, 12, 31)


def _items(net_income: float = 10.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Ordinary Shares Number": [100.0],
            "Total Debt": [50.0],
            "Cash And Cash Equivalents": [20.0],
            "Net Income": [net_income],
            "Common Stock Equity": [80.0],
            "EBITDA": [26.0],
            "Free Cash Flow": [8.0],
        },
        index=[YEAR_END],
    )


def test_multiples_use_reporting_currency() -> None:
    # Price TRY 40, FX 40 TRY/USD → market cap 40 × 100 / 40 = USD 100
    m = compute_multiples("TEST", "USD", price_try=40.0, fx_to_try=40.0, items=_items())
    assert m.market_cap_try_bn == pytest.approx(4000 / 1e9)
    assert m.pe == pytest.approx(10.0)
    assert m.pb == pytest.approx(1.25)
    assert m.ev_ebitda == pytest.approx((100 + 30) / 26)
    assert m.fcf_yield == pytest.approx(0.08)


def test_loss_makes_pe_meaningless() -> None:
    m = compute_multiples("TEST", "TRY", price_try=1.0, fx_to_try=1.0, items=_items(-5.0))
    assert math.isnan(m.pe)
