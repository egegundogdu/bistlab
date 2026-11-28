"""Risk report for stocks and a portfolio."""

from __future__ import annotations

import argparse

import pandas as pd
from sqlalchemy.orm import Session

from bistlab.data.db import get_engine
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
from bistlab.valuation.beta import load_closes


def risk_row(returns: pd.Series[float], risk_free: float, level: float) -> dict[str, float]:
    """Metrics of a single return series (in percent)."""
    return {
        "Annual return %": annualized_return(returns) * 100,
        "Volatility %": annualized_volatility(returns) * 100,
        "Sharpe": sharpe_ratio(returns, risk_free),
        "Max drawdown %": max_drawdown(returns) * 100,
        "Historical VaR %": historical_var(returns, level) * 100,
        "Normal VaR %": parametric_var(returns, level) * 100,
        "CVaR %": conditional_var(returns, level) * 100,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock and portfolio risk report.")
    parser.add_argument("tickers", nargs="+", help="Tickers, e.g. THYAO ASELS BIMAS")
    parser.add_argument("--weights", nargs="+", type=float, help="Weights (default equal)")
    parser.add_argument(
        "--benchmark", help="Benchmark index, e.g. XU100 (not part of the portfolio)"
    )
    parser.add_argument("--years", type=int, default=2, help="Years of data (default 2)")
    parser.add_argument("--risk-free", type=float, default=0.0, help="Annual risk-free rate")
    parser.add_argument("--level", type=float, default=0.95, help="VaR confidence level")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers]
    weights = args.weights or [1 / len(tickers)] * len(tickers)
    benchmark = args.benchmark.upper() if args.benchmark else None
    series = tickers + ([benchmark] if benchmark else [])

    with Session(get_engine()) as session:
        closes = pd.concat([load_closes(session, t) for t in series], axis=1, join="inner")
    cutoff = closes.index.max() - pd.Timedelta(days=365 * args.years)
    returns = daily_returns(closes[closes.index >= cutoff])

    rows = {t: risk_row(returns[t], args.risk_free, args.level) for t in tickers}
    portfolio = portfolio_returns(returns[tickers], weights)
    rows["PORTFOLIO"] = risk_row(portfolio, args.risk_free, args.level)
    if benchmark:
        rows[f"{benchmark} (benchmark)"] = risk_row(returns[benchmark], args.risk_free, args.level)
    table = pd.DataFrame(rows).T

    start, end = returns.index.min().date(), returns.index.max().date()
    print(f"Period: {start} → {end} ({len(returns)} trading days), nominal TRY")
    print(f"Weights: {dict(zip(tickers, [round(w, 3) for w in weights], strict=True))}")
    print(
        f"Risk-free rate: {args.risk_free * 100:.1f}% | VaR/CVaR: {args.level * 100:.0f}%, 1 day\n"
    )
    print(table.round(2).to_string())


if __name__ == "__main__":
    main()
