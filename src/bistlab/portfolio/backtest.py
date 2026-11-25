"""Yürüyen pencereli (walk-forward) portföy backtest motoru."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from bistlab.data.db import get_engine
from bistlab.portfolio.optimize import Vector, annual_stats, max_sharpe, min_variance
from bistlab.portfolio.risk import (
    annualized_return,
    annualized_volatility,
    daily_returns,
    max_drawdown,
    sharpe_ratio,
)
from bistlab.valuation.beta import load_closes

# Strateji: geçmiş getiri penceresinden hedef ağırlıkları üretir
Strategy = Callable[[pd.DataFrame], Vector]


@dataclass(frozen=True)
class BacktestResult:
    returns: pd.Series[float]
    average_turnover: float  # ilk alım hariç, yeniden dengeleme başına ortalama devir


def run_backtest(
    returns: pd.DataFrame,
    strategy: Strategy,
    lookback: int = 252,
    rebalance_every: int = 21,
    cost: float = 0.002,
) -> BacktestResult:
    """Her `rebalance_every` günde, sadece önceki `lookback` günü görerek yeniden dengeler.

    Yeniden dengelemeler arasında ağırlıklar fiyatlarla birlikte kayar.
    İşlem maliyeti = cost × Σ|yeni ağırlık - kaymış ağırlık|, o günün getirisinden düşülür.
    """
    if len(returns) <= lookback:
        raise ValueError("Backtest için geriye bakış penceresinden uzun veri gerekli.")
    values = returns.to_numpy(dtype=float)
    weights: Vector = np.zeros(values.shape[1], dtype=np.float64)
    daily: list[float] = []
    turnovers: list[float] = []

    for t in range(lookback, len(values)):
        cost_today = 0.0
        if (t - lookback) % rebalance_every == 0:
            target = np.asarray(strategy(returns.iloc[t - lookback : t]), dtype=np.float64)
            turnover = float(np.abs(target - weights).sum())
            turnovers.append(turnover)
            cost_today = cost * turnover
            weights = target
        day = values[t]
        daily.append(float(weights @ day) - cost_today)
        grown = weights * (1 + day)
        weights = np.asarray(grown / grown.sum(), dtype=np.float64)

    series = pd.Series(daily, index=returns.index[lookback:], dtype=float)
    rebalances = turnovers[1:] if len(turnovers) > 1 else turnovers
    return BacktestResult(series, float(np.mean(rebalances)))


def equal_weight(window: pd.DataFrame) -> Vector:
    """Her hisseye eşit ağırlık (1/N)."""
    n = window.shape[1]
    return np.asarray(np.full(n, 1.0 / n), dtype=np.float64)


def min_variance_strategy(max_weight: float) -> Strategy:
    def strategy(window: pd.DataFrame) -> Vector:
        mu, cov = annual_stats(window)
        return min_variance(mu, cov, max_weight).weights

    return strategy


def max_sharpe_strategy(risk_free: float, max_weight: float) -> Strategy:
    def strategy(window: pd.DataFrame) -> Vector:
        mu, cov = annual_stats(window)
        try:
            return max_sharpe(mu, cov, risk_free, max_weight).weights
        except RuntimeError:
            return equal_weight(window)  # optimizasyon yakınsamazsa eşit ağırlığa düş

    return strategy


def metrics(result: pd.Series[float], risk_free: float) -> dict[str, float]:
    return {
        "Yıllık getiri %": annualized_return(result) * 100,
        "Oynaklık %": annualized_volatility(result) * 100,
        "Sharpe": sharpe_ratio(result, risk_free),
        "Maks. düşüş %": max_drawdown(result) * 100,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stratejileri örneklem dışı karşılaştırır.")
    parser.add_argument("tickers", nargs="+", help="Hisse kodları")
    parser.add_argument("--benchmark", default="XU100", help="Kıyas endeksi")
    parser.add_argument("--lookback", type=int, default=252, help="Geriye bakış (işlem günü)")
    parser.add_argument("--rebalance", type=int, default=21, help="Yeniden dengeleme sıklığı")
    parser.add_argument("--cost", type=float, default=0.002, help="İşlem maliyeti (devir başına)")
    parser.add_argument("--max-weight", type=float, default=0.35, help="Tek hisse üst sınırı")
    parser.add_argument("--risk-free", type=float, default=0.0, help="Yıllık risksiz faiz")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers]
    benchmark = args.benchmark.upper()
    with Session(get_engine()) as session:
        closes = pd.concat(
            [load_closes(session, t) for t in [*tickers, benchmark]], axis=1, join="inner"
        )
    returns = daily_returns(closes)
    assets = returns[tickers]

    strategies: dict[str, Strategy] = {
        "Eşit ağırlık": equal_weight,
        "Min. varyans": min_variance_strategy(args.max_weight),
        "Maks. Sharpe": max_sharpe_strategy(args.risk_free, args.max_weight),
    }
    rows: dict[str, dict[str, float]] = {}
    for name, strategy in strategies.items():
        result = run_backtest(assets, strategy, args.lookback, args.rebalance, args.cost)
        rows[name] = metrics(result.returns, args.risk_free)
        rows[name]["Ort. devir %"] = result.average_turnover * 100
    bench = returns[benchmark].iloc[args.lookback :]
    rows[f"{benchmark} (kıyas)"] = metrics(bench, args.risk_free)
    rows[f"{benchmark} (kıyas)"]["Ort. devir %"] = 0.0

    start, end = bench.index.min().date(), bench.index.max().date()
    print(f"Örneklem dışı dönem: {start} → {end} ({len(bench)} işlem günü), TL nominal")
    print(
        f"Geriye bakış: {args.lookback} gün | Yeniden dengeleme: {args.rebalance} günde bir | "
        f"İşlem maliyeti: %{args.cost * 100:.2f} | Üst sınır: %{args.max_weight * 100:.0f}\n"
    )
    print(pd.DataFrame(rows).T.round(2).to_string())
    print("\nHisse listesi bugünden bakılarak seçildi; seçim yanlılığı sonuçları iyimser gösterir.")


if __name__ == "__main__":
    main()
