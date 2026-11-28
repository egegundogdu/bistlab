from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from bistlab.api import portfolio

KW = {"years": 2.0, "risk_free": 0.0, "level": 0.95, "max_weight": 1.0}


class Prices:
    """Tohumlu sentetik fiyatlar: AAA–BBB pozitif, CCC ortak faktöre ters (negatif) bağlı."""

    def __init__(self) -> None:
        rng = np.random.default_rng(7)
        days = pd.bdate_range("2024-01-01", periods=400)
        common = rng.normal(0, 0.01, len(days))
        noise = rng.normal(0, 0.01, (len(days), 3))
        rets = {
            "AAA": 0.0008 + common + noise[:, 0],
            "BBB": 0.0004 + common + noise[:, 1],
            "CCC": 0.0003 - common + noise[:, 2],
        }
        self.data = {k: pd.Series(100 * np.cumprod(1 + v), index=days) for k, v in rets.items()}

    def closes(self, ticker: str) -> pd.Series[float]:
        if ticker not in self.data:
            raise ValueError(f"{ticker}: fiyat yok")
        return self.data[ticker]


def test_equal_weights_skip_and_signs() -> None:
    out = portfolio.portfolio_risk(Prices(), ["AAA", "BBB", "CCC", "YOK"], None, **KW)
    assert out.tickers == ["AAA", "BBB", "CCC"]
    assert out.skipped == ["YOK"]
    assert out.weights == pytest.approx([1 / 3] * 3)
    assert out.cvar >= out.var_historical > 0
    assert out.max_drawdown <= 0


def test_correlation_and_diversification() -> None:
    out = portfolio.portfolio_risk(Prices(), ["AAA", "BBB", "CCC"], None, **KW)
    corr = np.asarray(out.correlation)
    assert corr.diagonal() == pytest.approx([1.0, 1.0, 1.0])
    assert corr[0, 1] > 0.3
    assert corr[0, 2] < -0.3
    # negatif korelasyonlu hisse eklenince portföy oynaklığı tek tek hisselerin altına iner
    assert out.volatility < min(out.asset_volatility)


def test_weights_normalized_and_optimizers() -> None:
    kw = {**KW, "max_weight": 0.6}
    out = portfolio.portfolio_risk(Prices(), ["AAA", "BBB", "CCC"], [2.0, 1.0, 1.0], **kw)
    assert out.weights == pytest.approx([0.5, 0.25, 0.25])
    assert sum(out.min_variance.weights) == pytest.approx(1.0)
    assert max(out.max_sharpe.weights) <= 0.6 + 1e-6
    assert out.min_variance.volatility <= out.current.volatility + 1e-6
    assert out.max_sharpe.sharpe >= out.current.sharpe - 1e-4
    assert out.frontier[0].volatility == pytest.approx(out.min_variance.volatility, rel=1e-3)


def test_bad_inputs() -> None:
    src = Prices()
    with pytest.raises(ValueError, match="at least two"):
        portfolio.portfolio_risk(src, ["AAA", "YOK"], None, **KW)
    with pytest.raises(ValueError, match="Number of weights"):
        portfolio.portfolio_risk(src, ["AAA", "BBB"], [1.0], **KW)
    with pytest.raises(ValueError, match="negative"):
        portfolio.portfolio_risk(src, ["AAA", "BBB"], [1.0, -1.0], **KW)
    with pytest.raises(ValueError):  # 3 hisse × 0,2 < 1: ağırlıklar 1'e tamamlanamaz
        portfolio.portfolio_risk(src, ["AAA", "BBB", "CCC"], None, **{**KW, "max_weight": 0.2})
