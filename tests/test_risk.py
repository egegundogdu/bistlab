import numpy as np
import pandas as pd
import pytest

from bistlab.portfolio.risk import (
    annualized_return,
    annualized_volatility,
    conditional_var,
    historical_var,
    max_drawdown,
    parametric_var,
    portfolio_returns,
)


def test_annualized_return_of_constant_daily_return() -> None:
    r = pd.Series([0.001] * 252)
    assert annualized_return(r) == pytest.approx(1.001**252 - 1)


def test_annualized_volatility_matches_definition() -> None:
    r = pd.Series([0.01, -0.01] * 50)
    assert annualized_volatility(r) == pytest.approx(np.std(r, ddof=1) * np.sqrt(252))


def test_max_drawdown() -> None:
    # Servet 1,10 → 0,88 → 0,924; zirve 1,10, dip 0,88 → %-20
    assert max_drawdown(pd.Series([0.10, -0.20, 0.05])) == pytest.approx(-0.20)


def test_historical_var_and_cvar() -> None:
    # -%5'ten +%14'e 20 eşit aralıklı getiri; %5'lik dilim (doğrusal) = -0,0405
    r = pd.Series(np.round(np.arange(-0.05, 0.15, 0.01), 4))
    assert historical_var(r) == pytest.approx(0.0405)
    assert conditional_var(r) == pytest.approx(0.05)


def test_parametric_var_uses_normal_quantile() -> None:
    r = pd.Series([0.01, -0.01] * 500)
    expected = 1.6448536 * r.std(ddof=1) - r.mean()
    assert parametric_var(r) == pytest.approx(expected, rel=1e-6)


def test_portfolio_returns_weighted_sum() -> None:
    returns = pd.DataFrame({"A": [0.10, 0.20], "B": [0.00, 0.10]})
    assert list(portfolio_returns(returns, [0.5, 0.5])) == pytest.approx([0.05, 0.15])
    with pytest.raises(ValueError):
        portfolio_returns(returns, [0.7, 0.7])
