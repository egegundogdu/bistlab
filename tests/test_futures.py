import numpy as np
import pandas as pd
import pytest

from bistlab.derivatives.futures import (
    contracts_needed,
    implied_rate,
    min_variance_hedge,
    theoretical_price,
)


def test_theoretical_price_cost_of_carry() -> None:
    # 100 × 1,40^0,5 ≈ 118,32
    assert theoretical_price(100.0, 0.5, 0.40) == pytest.approx(100 * 1.4**0.5)
    # A dividend yield lowers the futures price
    assert theoretical_price(100.0, 0.5, 0.40, 0.05) < theoretical_price(100.0, 0.5, 0.40)


def test_implied_rate_roundtrip() -> None:
    f = theoretical_price(250.0, 0.25, 0.35, 0.03)
    assert implied_rate(f, 250.0, 0.25, 0.03) == pytest.approx(0.35)


def test_hedge_ratio_equals_beta_and_removes_market_risk() -> None:
    rng = np.random.default_rng(7)
    index = pd.date_range("2025-01-01", periods=250, freq="B")
    market = pd.Series(rng.normal(0, 0.02, 250), index=index)
    asset = 1.2 * market
    result = min_variance_hedge(asset, market)
    assert result.ratio == pytest.approx(1.2)
    assert result.hedged_vol == pytest.approx(0.0, abs=1e-12)
    assert result.risk_reduction == pytest.approx(1.0)


def test_partial_hedge_with_idiosyncratic_risk() -> None:
    rng = np.random.default_rng(11)
    index = pd.date_range("2025-01-01", periods=500, freq="B")
    market = pd.Series(rng.normal(0, 0.02, 500), index=index)
    asset = market + pd.Series(rng.normal(0, 0.02, 500), index=index)
    result = min_variance_hedge(asset, market)
    assert 0 < result.risk_reduction < 1  # company-specific risk cannot be hedged


def test_contracts_needed() -> None:
    assert contracts_needed(1_200_000, 10_000, 10) == pytest.approx(12)
    with pytest.raises(ValueError):
        contracts_needed(1_000_000, 10_000, 0)


def test_non_positive_maturity_raises() -> None:
    with pytest.raises(ValueError):
        theoretical_price(100.0, 0.0, 0.40)
