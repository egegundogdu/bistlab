"""Return and risk metrics: volatility, Sharpe, maximum drawdown, VaR, CVaR."""

from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import NormalDist

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def daily_returns(closes: pd.DataFrame) -> pd.DataFrame:
    """Daily simple returns from a close table (columns: stocks); only days common to all."""
    return (closes / closes.shift(1) - 1).dropna(how="any")


def portfolio_returns(returns: pd.DataFrame, weights: Sequence[float]) -> pd.Series[float]:
    """Return of a daily-rebalanced portfolio: Σ weight × stock return."""
    if len(weights) != returns.shape[1]:
        raise ValueError("Number of weights must equal the number of stocks.")
    if abs(sum(weights) - 1) > 1e-9:
        raise ValueError("Weights must sum to 1.")
    w = pd.Series(list(weights), index=returns.columns)
    return returns.mul(w, axis=1).sum(axis=1)


def annualized_return(returns: pd.Series[float], periods: int = TRADING_DAYS) -> float:
    """Compound annual return."""
    growth = float(np.prod((1 + returns).to_numpy()))
    return float(growth ** (periods / len(returns))) - 1


def annualized_volatility(returns: pd.Series[float], periods: int = TRADING_DAYS) -> float:
    """Annual volatility: daily standard deviation × √252."""
    return float(returns.std(ddof=1)) * math.sqrt(periods)


def sharpe_ratio(
    returns: pd.Series[float], risk_free: float = 0.0, periods: int = TRADING_DAYS
) -> float:
    """(Annual return - annual risk-free rate) / annual volatility."""
    return (annualized_return(returns, periods) - risk_free) / annualized_volatility(
        returns, periods
    )


def max_drawdown(returns: pd.Series[float]) -> float:
    """Largest peak-to-trough fall of the wealth curve (a negative number)."""
    wealth = (1 + returns).cumprod()
    return float((wealth / wealth.cummax() - 1).min())


def historical_var(returns: pd.Series[float], level: float = 0.95) -> float:
    """Historical VaR: the (1 - level) quantile return expressed as a loss (positive number)."""
    return -float(returns.quantile(1 - level))


def parametric_var(returns: pd.Series[float], level: float = 0.95) -> float:
    """Parametric (normal) VaR: -(mean + z × standard deviation)."""
    z = NormalDist().inv_cdf(1 - level)
    return -(float(returns.mean()) + z * float(returns.std(ddof=1)))


def conditional_var(returns: pd.Series[float], level: float = 0.95) -> float:
    """CVaR (expected shortfall): mean loss on days beyond VaR (positive number)."""
    threshold = -historical_var(returns, level)
    tail = returns[returns <= threshold]
    return -float(tail.mean())
