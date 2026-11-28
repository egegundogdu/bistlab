"""Markowitz mean-variance optimisation and the efficient frontier."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy.optimize import minimize
from sqlalchemy.orm import Session

from bistlab.data.db import get_engine
from bistlab.portfolio.risk import TRADING_DAYS, daily_returns
from bistlab.valuation.beta import load_closes

Vector = npt.NDArray[np.float64]


@dataclass(frozen=True)
class Portfolio:
    weights: Vector
    expected_return: float
    volatility: float

    def sharpe(self, risk_free: float = 0.0) -> float:
        return (self.expected_return - risk_free) / self.volatility


def annual_stats(returns: pd.DataFrame, periods: int = TRADING_DAYS) -> tuple[Vector, Vector]:
    """Annual expected return vector (arithmetic mean × 252) and covariance matrix."""
    mu = np.asarray(returns.mean().to_numpy(dtype=float) * periods, dtype=np.float64)
    cov = np.asarray(returns.cov().to_numpy(dtype=float) * periods, dtype=np.float64)
    return mu, cov


def performance(weights: Vector, mu: Vector, cov: Vector) -> Portfolio:
    """Expected return and volatility of a portfolio from its weights."""
    expected = float(weights @ mu)
    volatility = float(np.sqrt(weights @ cov @ weights))
    return Portfolio(np.asarray(weights, dtype=np.float64), expected, volatility)


def _solve(
    objective: Callable[[Vector], float],
    n: int,
    max_weight: float,
    constraints: list[dict[str, Any]] | None = None,
) -> Vector:
    """Minimises the objective with weights summing to 1, each in [0, max_weight]."""
    if max_weight * n < 1 - 1e-9:
        raise ValueError(
            "Max weight × number of stocks must be at least 1; weights cannot sum to 1."
        )
    cons: list[dict[str, Any]] = [{"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0}]
    cons += constraints or []
    start = np.asarray(np.full(n, 1.0 / n), dtype=np.float64)
    result = minimize(
        objective, start, method="SLSQP", bounds=[(0.0, max_weight)] * n, constraints=cons
    )
    if not result.success:
        raise RuntimeError(f"Optimisation failed: {result.message}")
    weights = np.clip(np.asarray(result.x, dtype=np.float64), 0.0, None)
    return np.asarray(weights / weights.sum(), dtype=np.float64)


def min_variance(mu: Vector, cov: Vector, max_weight: float = 1.0) -> Portfolio:
    """Lowest-volatility portfolio."""
    weights = _solve(lambda w: float(w @ cov @ w), len(mu), max_weight)
    return performance(weights, mu, cov)


def max_sharpe(
    mu: Vector, cov: Vector, risk_free: float = 0.0, max_weight: float = 1.0
) -> Portfolio:
    """Highest-Sharpe (tangency) portfolio."""

    def negative_sharpe(w: Vector) -> float:
        p = performance(w, mu, cov)
        return -(p.expected_return - risk_free) / p.volatility

    return performance(_solve(negative_sharpe, len(mu), max_weight), mu, cov)


def max_return(mu: Vector, cov: Vector, max_weight: float = 1.0) -> Portfolio:
    """Highest return under the cap: fills the best stocks up to the cap, in order."""
    weights = np.zeros(len(mu), dtype=np.float64)
    remaining = 1.0
    for i in np.argsort(mu)[::-1]:
        take = min(max_weight, remaining)
        weights[i] = take
        remaining -= take
        if remaining <= 1e-12:
            break
    return performance(weights, mu, cov)


def efficient_frontier(
    mu: Vector, cov: Vector, points: int = 8, max_weight: float = 1.0
) -> list[Portfolio]:
    """From min variance to max return: the lowest-risk portfolio for each target return."""
    low = min_variance(mu, cov, max_weight)
    high = max_return(mu, cov, max_weight)
    frontier = [low]
    for target in np.linspace(low.expected_return, high.expected_return, points)[1:-1]:
        constraint = {"type": "eq", "fun": lambda w, t=target: float(w @ mu) - t}
        weights = _solve(lambda w: float(w @ cov @ w), len(mu), max_weight, [constraint])
        frontier.append(performance(weights, mu, cov))
    frontier.append(high)
    return frontier


def main() -> None:
    parser = argparse.ArgumentParser(description="Markowitz optimisation and efficient frontier.")
    parser.add_argument("tickers", nargs="+", help="Tickers")
    parser.add_argument("--years", type=int, default=2, help="Years of data (default 2)")
    parser.add_argument("--risk-free", type=float, default=0.0, help="Annual risk-free rate")
    parser.add_argument("--max-weight", type=float, default=0.35, help="Max weight per stock")
    parser.add_argument("--points", type=int, default=8, help="Number of frontier points")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers]
    with Session(get_engine()) as session:
        closes = pd.concat([load_closes(session, t) for t in tickers], axis=1, join="inner")
    cutoff = closes.index.max() - pd.Timedelta(days=365 * args.years)
    returns = daily_returns(closes[closes.index >= cutoff])
    mu, cov = annual_stats(returns)

    n = len(tickers)
    portfolios = {
        "Equal weight": performance(np.full(n, 1.0 / n), mu, cov),
        "Min. variance": min_variance(mu, cov, args.max_weight),
        "Max. Sharpe": max_sharpe(mu, cov, args.risk_free, args.max_weight),
    }

    weights = pd.DataFrame({k: p.weights * 100 for k, p in portfolios.items()}, index=tickers)
    summary = pd.DataFrame(
        {
            k: [p.expected_return * 100, p.volatility * 100, p.sharpe(args.risk_free)]
            for k, p in portfolios.items()
        },
        index=["Expected return %", "Volatility %", "Sharpe"],
    )
    start, end = returns.index.min().date(), returns.index.max().date()
    print(f"Period: {start} → {end} ({len(returns)} days), nominal TRY, arithmetic annual mean")
    print(f"Max weight per stock: {args.max_weight * 100:.0f}% | Risk-free rate: ", end="")
    print(f"{args.risk_free * 100:.1f}%\n")
    print("Weights (%):")
    print(weights.round(1).to_string())
    print()
    print(summary.round(2).to_string())

    frontier = efficient_frontier(mu, cov, args.points, args.max_weight)
    rows = [(p.volatility * 100, p.expected_return * 100) for p in frontier]
    print("\nEfficient frontier:")
    print(pd.DataFrame(rows, columns=["Volatility %", "Return %"]).round(2).to_string(index=False))
    print("\nPast returns do not predict future returns; results are very sensitive to inputs.")


if __name__ == "__main__":
    main()
