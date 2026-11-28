"""Walk-forward portfolio backtest engine."""

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

# Strategy: produces target weights from a window of past returns
Strategy = Callable[[pd.DataFrame], Vector]


@dataclass(frozen=True)
class BacktestResult:
    returns: pd.Series[float]
    average_turnover: float  # mean turnover per rebalance, excluding the initial purchase


def run_backtest(
    returns: pd.DataFrame,
    strategy: Strategy,
    lookback: int = 252,
    rebalance_every: int = 21,
    cost: float = 0.002,
) -> BacktestResult:
    """Rebalances every `rebalance_every` days, seeing only the previous `lookback` days.

    Between rebalances the weights drift with prices.
    Transaction cost = cost × Σ|new weight - drifted weight|, deducted from that day's return.
    """
    if len(returns) <= lookback:
        raise ValueError("Backtest needs more data than the lookback window.")
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
    """Equal weight for every stock (1/N)."""
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
            return equal_weight(window)  # fall back to equal weight if the optimiser fails

    return strategy


def metrics(result: pd.Series[float], risk_free: float) -> dict[str, float]:
    return {
        "Annual return %": annualized_return(result) * 100,
        "Volatility %": annualized_volatility(result) * 100,
        "Sharpe": sharpe_ratio(result, risk_free),
        "Max drawdown %": max_drawdown(result) * 100,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Out-of-sample comparison of strategies.")
    parser.add_argument("tickers", nargs="+", help="Tickers")
    parser.add_argument("--benchmark", default="XU100", help="Benchmark index")
    parser.add_argument("--lookback", type=int, default=252, help="Lookback (trading days)")
    parser.add_argument("--rebalance", type=int, default=21, help="Rebalance frequency (days)")
    parser.add_argument(
        "--cost", type=float, default=0.002, help="Transaction cost (per unit of turnover)"
    )
    parser.add_argument("--max-weight", type=float, default=0.35, help="Max weight per stock")
    parser.add_argument("--risk-free", type=float, default=0.0, help="Annual risk-free rate")
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
        "Equal weight": equal_weight,
        "Min. variance": min_variance_strategy(args.max_weight),
        "Max. Sharpe": max_sharpe_strategy(args.risk_free, args.max_weight),
    }
    rows: dict[str, dict[str, float]] = {}
    for name, strategy in strategies.items():
        result = run_backtest(assets, strategy, args.lookback, args.rebalance, args.cost)
        rows[name] = metrics(result.returns, args.risk_free)
        rows[name]["Avg. turnover %"] = result.average_turnover * 100
    bench = returns[benchmark].iloc[args.lookback :]
    rows[f"{benchmark} (benchmark)"] = metrics(bench, args.risk_free)
    rows[f"{benchmark} (benchmark)"]["Avg. turnover %"] = 0.0

    start, end = bench.index.min().date(), bench.index.max().date()
    print(f"Out-of-sample period: {start} → {end} ({len(bench)} trading days), nominal TRY")
    print(
        f"Lookback: {args.lookback} days | Rebalance: every {args.rebalance} days | "
        f"Transaction cost: {args.cost * 100:.2f}% | Max weight: {args.max_weight * 100:.0f}%\n"
    )
    print(pd.DataFrame(rows).T.round(2).to_string())
    print("\nTickers were picked with hindsight; selection bias flatters the results.")


if __name__ == "__main__":
    main()
