"""Futures: cost-of-carry model, basis and minimum-variance hedge."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass

import pandas as pd
from sqlalchemy.orm import Session

from bistlab.data.db import get_engine
from bistlab.portfolio.risk import TRADING_DAYS, daily_returns, portfolio_returns
from bistlab.valuation.beta import beta, load_closes


def _check_years(years: float) -> None:
    if years <= 0:
        raise ValueError("Maturity must be positive.")


def theoretical_price(spot: float, years: float, rate: float, dividend_yield: float = 0.0) -> float:
    """Cost of carry: F = S × ((1 + r) / (1 + q))^T; r and q are annual effective rates."""
    _check_years(years)
    return spot * float(((1 + rate) / (1 + dividend_yield)) ** years)


def implied_rate(futures: float, spot: float, years: float, dividend_yield: float = 0.0) -> float:
    """Annual effective financing rate implied by the futures price."""
    _check_years(years)
    return float((futures / spot) ** (1 / years)) * (1 + dividend_yield) - 1


@dataclass(frozen=True)
class HedgeResult:
    ratio: float  # futures notional to sell per 1 TRY of the asset
    unhedged_vol: float
    hedged_vol: float

    @property
    def risk_reduction(self) -> float:
        """Relative reduction in volatility."""
        return 1 - self.hedged_vol / self.unhedged_vol


def min_variance_hedge(
    asset_returns: pd.Series[float], hedge_returns: pd.Series[float]
) -> HedgeResult:
    """Minimum-variance hedge ratio = Cov / Var, i.e. the asset's beta to the hedge."""
    joined = pd.concat([asset_returns, hedge_returns], axis=1, join="inner").dropna()
    asset, hedge = joined.iloc[:, 0], joined.iloc[:, 1]
    ratio = beta(asset, hedge)
    hedged = asset - ratio * hedge
    scale = math.sqrt(TRADING_DAYS)
    return HedgeResult(ratio, float(asset.std(ddof=1)) * scale, float(hedged.std(ddof=1)) * scale)


def contracts_needed(notional: float, futures_price: float, multiplier: float) -> float:
    """Contracts needed = hedge notional / (futures price × contract multiplier)."""
    if futures_price <= 0 or multiplier <= 0:
        raise ValueError("Futures price and contract multiplier must be positive.")
    return notional / (futures_price * multiplier)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hedge a stock portfolio with index futures.")
    parser.add_argument("tickers", nargs="+", help="Stocks in the portfolio (equal weight)")
    parser.add_argument("--value", type=float, default=1_000_000, help="Portfolio value (TRY)")
    parser.add_argument("--index", default="XU030", help="Underlying index of the futures")
    parser.add_argument("--days", type=int, default=60, help="Calendar days to maturity")
    parser.add_argument("--rate", type=float, default=0.40, help="Annual effective interest rate")
    parser.add_argument("--dividend-yield", type=float, default=0.0, help="Index dividend yield")
    parser.add_argument("--years", type=int, default=1, help="Years of data for the hedge ratio")
    parser.add_argument("--multiplier", type=float, help="Contract multiplier (check on VIOP)")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers]
    index = args.index.upper()
    with Session(get_engine()) as session:
        closes = pd.concat(
            [load_closes(session, t) for t in [*tickers, index]], axis=1, join="inner"
        )
    cutoff = closes.index.max() - pd.Timedelta(days=365 * args.years)
    returns = daily_returns(closes[closes.index >= cutoff])
    portfolio = portfolio_returns(returns[tickers], [1 / len(tickers)] * len(tickers))
    hedge = min_variance_hedge(portfolio, returns[index])

    spot = float(closes[index].iloc[-1])
    years = args.days / 365
    futures = theoretical_price(spot, years, args.rate, args.dividend_yield)
    notional = hedge.ratio * args.value

    print(f"Portfolio: {', '.join(tickers)} (equal weight) | value {args.value:,.0f} TRY")
    print(f"{index} spot: {spot:,.2f} | maturity {args.days} days | rate {args.rate * 100:.1f}%\n")
    print(f"Theoretical futures price: {futures:,.2f}")
    print(f"Basis (F - S): {futures - spot:,.2f} points ({(futures / spot - 1) * 100:.2f}%)")
    print(f"Check: implied rate {implied_rate(futures, spot, years) * 100:.1f}%\n")
    print(f"Hedge ratio (beta, last {args.years} years, daily): {hedge.ratio:.3f}")
    print(f"Futures notional to sell: {notional:,.0f} TRY")
    if args.multiplier:
        count = contracts_needed(notional, futures, args.multiplier)
        print(f"Contracts needed: {count:,.1f} → rounded {round(count)}")
    print(f"\nVolatility (annual): unhedged {hedge.unhedged_vol * 100:.1f}%", end="")
    print(f" → hedged {hedge.hedged_vol * 100:.1f}% (reduction {hedge.risk_reduction * 100:.0f}%)")
    print("\nNote: the futures price is theoretical; the market price can differ by the basis.")
    print("Risk left after hedging is company-specific (not explained by the index).")


if __name__ == "__main__":
    main()
