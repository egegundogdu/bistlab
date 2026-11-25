"""Getiri ve risk metrikleri: oynaklık, Sharpe, maksimum düşüş, VaR, CVaR."""

from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import NormalDist

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def daily_returns(closes: pd.DataFrame) -> pd.DataFrame:
    """Kapanış tablosundan (sütun: hisse) günlük basit getiriler; tüm hisselerin ortak günleri."""
    return (closes / closes.shift(1) - 1).dropna(how="any")


def portfolio_returns(returns: pd.DataFrame, weights: Sequence[float]) -> pd.Series[float]:
    """Günlük yeniden dengelenen portföyün getirisi: Σ ağırlık × hisse getirisi."""
    if len(weights) != returns.shape[1]:
        raise ValueError("Ağırlık sayısı hisse sayısına eşit olmalı.")
    if abs(sum(weights) - 1) > 1e-9:
        raise ValueError("Ağırlıkların toplamı 1 olmalı.")
    w = pd.Series(list(weights), index=returns.columns)
    return returns.mul(w, axis=1).sum(axis=1)


def annualized_return(returns: pd.Series[float], periods: int = TRADING_DAYS) -> float:
    """Bileşik yıllık getiri."""
    growth = float(np.prod((1 + returns).to_numpy()))
    return float(growth ** (periods / len(returns))) - 1


def annualized_volatility(returns: pd.Series[float], periods: int = TRADING_DAYS) -> float:
    """Yıllık oynaklık: günlük standart sapma × √252."""
    return float(returns.std(ddof=1)) * math.sqrt(periods)


def sharpe_ratio(
    returns: pd.Series[float], risk_free: float = 0.0, periods: int = TRADING_DAYS
) -> float:
    """(Yıllık getiri - yıllık risksiz faiz) / yıllık oynaklık."""
    return (annualized_return(returns, periods) - risk_free) / annualized_volatility(
        returns, periods
    )


def max_drawdown(returns: pd.Series[float]) -> float:
    """Servet eğrisinin zirveden dibe en büyük düşüşü (negatif sayı)."""
    wealth = (1 + returns).cumprod()
    return float((wealth / wealth.cummax() - 1).min())


def historical_var(returns: pd.Series[float], level: float = 0.95) -> float:
    """Tarihsel VaR: (1 - level) dilimindeki getirinin kayıp olarak ifadesi (pozitif sayı)."""
    return -float(returns.quantile(1 - level))


def parametric_var(returns: pd.Series[float], level: float = 0.95) -> float:
    """Parametrik (normal dağılım) VaR: -(ortalama + z × standart sapma)."""
    z = NormalDist().inv_cdf(1 - level)
    return -(float(returns.mean()) + z * float(returns.std(ddof=1)))


def conditional_var(returns: pd.Series[float], level: float = 0.95) -> float:
    """CVaR (beklenen kayıp): VaR'ı aşan günlerin ortalama kaybı (pozitif sayı)."""
    threshold = -historical_var(returns, level)
    tail = returns[returns <= threshold]
    return -float(tail.mean())
