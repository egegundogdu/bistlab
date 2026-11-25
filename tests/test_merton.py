import math

import pandas as pd
import pytest

from bistlab.credit.merton import default_point, latest_debt, merton_equity, solve_merton


def test_default_point() -> None:
    assert default_point(100, 200) == 200


def test_merton_equity_is_call_on_assets() -> None:
    # Borç sıfıra yakınsa hisse ≈ varlık, hisse oynaklığı ≈ varlık oynaklığı
    equity, equity_vol = merton_equity(100.0, 0.3, 1e-9, 0.05)
    assert equity == pytest.approx(100.0, rel=1e-6)
    assert equity_vol == pytest.approx(0.3, rel=1e-6)


def test_solve_merton_recovers_assets() -> None:
    value, vol, debt, rate = 150.0, 0.25, 80.0, 0.30
    equity, equity_vol = merton_equity(value, vol, debt, rate)
    result = solve_merton(equity, equity_vol, debt, rate)
    assert result.asset_value == pytest.approx(value, rel=1e-4)
    assert result.asset_vol == pytest.approx(vol, rel=1e-4)
    assert 0 < result.default_probability < 1


def test_more_debt_means_higher_default_probability() -> None:
    low = solve_merton(100.0, 0.4, 50.0, 0.3)
    high = solve_merton(100.0, 0.4, 200.0, 0.3)
    assert high.default_probability > low.default_probability
    assert high.distance_to_default < low.distance_to_default


def test_latest_debt_uses_last_period() -> None:
    items = pd.DataFrame(
        {"Total Debt": [100.0, 300.0], "Current Debt": [40.0, 120.0]},
        index=["2024-12-31", "2025-12-31"],
    )
    period, short, long = latest_debt(items)
    assert period == "2025-12-31"
    assert (short, long) == (120.0, 180.0)
    assert not math.isnan(short)
