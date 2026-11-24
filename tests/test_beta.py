import numpy as np
import pandas as pd
import pytest

from bistlab.valuation.beta import beta, weekly_returns


def test_beta_recovers_known_slope() -> None:
    rng = np.random.default_rng(42)
    index = pd.date_range("2024-01-05", periods=100, freq="W-FRI")
    market = pd.Series(rng.normal(0, 0.03, 100), index=index)
    stock = 1.5 * market + 0.001
    assert beta(stock, market) == pytest.approx(1.5)


def test_beta_requires_enough_overlap() -> None:
    index = pd.date_range("2024-01-05", periods=10, freq="W-FRI")
    returns = pd.Series(np.linspace(0.01, 0.1, 10), index=index)
    with pytest.raises(ValueError):
        beta(returns, returns)


def test_weekly_returns_use_friday_closes() -> None:
    days = pd.bdate_range("2024-01-01", "2024-01-19")
    closes = pd.Series(range(1, len(days) + 1), index=days, dtype=float)
    # Cuma kapanışları 5, 10, 15 → getiriler 10/5 - 1 = 1,0 ve 15/10 - 1 = 0,5
    assert list(weekly_returns(closes).round(6)) == [1.0, 0.5]
