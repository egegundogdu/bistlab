"""Portföy risk uç noktasının çekirdeği: ağırlıklar → risk ölçüleri, korelasyon, Markowitz.

Yeni hesap yok; ``bistlab.portfolio`` fonksiyonları ortak tarih aralığına hizalanmış
günlük getirilerle çağrılır. Veri kaynağı yalnızca ``closes(ticker)`` sağlamalı (DB'siz test).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np
import numpy.typing as npt
import pandas as pd

from bistlab.api.schemas import FrontierPoint, PortfolioOut
from bistlab.portfolio.optimize import (
    Portfolio,
    annual_stats,
    efficient_frontier,
    max_sharpe,
    min_variance,
    performance,
)
from bistlab.portfolio.risk import (
    annualized_return,
    annualized_volatility,
    conditional_var,
    daily_returns,
    historical_var,
    max_drawdown,
    parametric_var,
    portfolio_returns,
    sharpe_ratio,
)

MIN_OBSERVATIONS = 20


class PriceSource(Protocol):
    def closes(self, ticker: str) -> pd.Series[float]: ...


def aligned_returns(
    source: PriceSource, tickers: Sequence[str], years: float
) -> tuple[pd.DataFrame, list[str]]:
    """Fiyatları ortak tarihlere hizalar, son ``years`` yılı alır, günlük getiri döndürür."""
    series: dict[str, pd.Series[float]] = {}
    skipped: list[str] = []
    for ticker in tickers:
        try:
            closes = source.closes(ticker)
        except (ValueError, KeyError):
            skipped.append(ticker)
            continue
        if len(closes) < 2:
            skipped.append(ticker)
            continue
        series[ticker] = closes
    if len(series) < 2:
        raise ValueError("Prices are required for at least two stocks.")
    frame = pd.DataFrame(series)
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index().dropna()
    if frame.empty:
        raise ValueError("The stocks have no common trading days.")
    end = pd.Timestamp(frame.index.max())
    frame = frame[frame.index >= end - pd.Timedelta(days=int(years * 365.25))]
    returns = daily_returns(frame)
    if len(returns) < MIN_OBSERVATIONS:
        raise ValueError(
            f"Not enough observations in the common range (at least {MIN_OBSERVATIONS} days)."
        )
    return returns, skipped


def normalized_weights(
    tickers: Sequence[str], names: Sequence[str], weights: Sequence[float] | None
) -> npt.NDArray[np.float64]:
    """Boşsa eşit ağırlık; değilse tickers sırasıyla eşleştirip toplamı 1'e ölçekler."""
    if not weights:
        return np.full(len(names), 1.0 / len(names), dtype=np.float64)
    if len(weights) != len(tickers):
        raise ValueError("Number of weights must match the number of tickers.")
    by_ticker = dict(zip(tickers, weights, strict=True))
    w = np.asarray([by_ticker[name] for name in names], dtype=np.float64)
    if (w < 0).any():
        raise ValueError("Weights cannot be negative (no short selling).")
    total = float(w.sum())
    if total <= 0:
        raise ValueError("Weights must sum to a positive number.")
    return np.asarray(w / total, dtype=np.float64)


def point(p: Portfolio, risk_free: float) -> FrontierPoint:
    return FrontierPoint(
        weights=[float(x) for x in p.weights],
        expected_return=float(p.expected_return),
        volatility=float(p.volatility),
        sharpe=float(p.sharpe(risk_free)),
    )


def portfolio_risk(
    source: PriceSource,
    tickers: Sequence[str],
    weights: Sequence[float] | None,
    *,
    years: float,
    risk_free: float,
    level: float,
    max_weight: float,
) -> PortfolioOut:
    returns, skipped = aligned_returns(source, tickers, years)
    names = [str(c) for c in returns.columns]
    w = normalized_weights(tickers, names, weights)
    realized = portfolio_returns(returns, [float(x) for x in w])

    mu, cov = annual_stats(returns)
    vols = np.sqrt(np.diag(cov))
    corr = returns.corr().to_numpy(dtype=float)

    return PortfolioOut(
        tickers=names,
        skipped=skipped,
        start=pd.Timestamp(returns.index.min()).date().isoformat(),
        end=pd.Timestamp(returns.index.max()).date().isoformat(),
        observations=len(returns),
        risk_free=risk_free,
        level=level,
        weights=[float(x) for x in w],
        annual_return=float(annualized_return(realized)),
        volatility=float(annualized_volatility(realized)),
        sharpe=float(sharpe_ratio(realized, risk_free)),
        max_drawdown=float(max_drawdown(realized)),
        var_historical=float(historical_var(realized, level)),
        var_parametric=float(parametric_var(realized, level)),
        cvar=float(conditional_var(realized, level)),
        asset_return=[float(x) for x in mu],
        asset_volatility=[float(x) for x in vols],
        correlation=[[float(x) for x in row] for row in corr],
        current=point(performance(w, mu, cov), risk_free),
        min_variance=point(min_variance(mu, cov, max_weight), risk_free),
        max_sharpe=point(max_sharpe(mu, cov, risk_free, max_weight), risk_free),
        frontier=[
            point(p, risk_free)
            for p in efficient_frontier(mu, cov, points=12, max_weight=max_weight)
        ],
    )
