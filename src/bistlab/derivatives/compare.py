"""Prices the same option with Black-Scholes, a binomial tree and Monte Carlo."""

from __future__ import annotations

import argparse
import math

import pandas as pd
from sqlalchemy.orm import Session

from bistlab.data.db import get_engine
from bistlab.derivatives.binomial import binomial_price
from bistlab.derivatives.black_scholes import OptionType, bs_price
from bistlab.derivatives.monte_carlo import monte_carlo_price
from bistlab.portfolio.risk import annualized_volatility
from bistlab.valuation.beta import load_closes


def main() -> None:
    parser = argparse.ArgumentParser(description="Option price with three methods.")
    parser.add_argument(
        "--ticker", help="Underlying stock; last price and historical vol. come from it"
    )
    parser.add_argument("--spot", type=float, help="Underlying price (required without --ticker)")
    parser.add_argument("--strike", type=float, help="Strike (default: spot)")
    parser.add_argument("--days", type=int, default=180, help="Calendar days to maturity")
    parser.add_argument(
        "--rate", type=float, default=0.40, help="Annual risk-free rate (effective)"
    )
    parser.add_argument(
        "--vol", type=float, help="Annual volatility (historical when --ticker is given)"
    )
    parser.add_argument("--steps", type=int, default=1000, help="Binomial tree steps")
    parser.add_argument("--paths", type=int, default=200_000, help="Monte Carlo paths")
    args = parser.parse_args()

    spot, vol = args.spot, args.vol
    if args.ticker:
        with Session(get_engine()) as session:
            closes = load_closes(session, args.ticker)
        spot = spot or float(closes.iloc[-1])
        if vol is None:
            last_year = closes.iloc[-253:]
            vol = annualized_volatility((last_year / last_year.shift(1) - 1).dropna())
    if spot is None or vol is None:
        parser.error("give --ticker, or --spot and --vol.")

    strike = args.strike or spot
    years = args.days / 365
    rate = math.log1p(args.rate)

    rows = {}
    for option in ("call", "put"):
        opt: OptionType = option
        european = binomial_price(spot, strike, years, rate, vol, opt, steps=args.steps)
        american = binomial_price(
            spot, strike, years, rate, vol, opt, steps=args.steps, american=True
        )
        mc = monte_carlo_price(spot, strike, years, rate, vol, opt, paths=args.paths)
        low, high = mc.confidence_interval()
        rows[option.upper()] = {
            "Black-Scholes": bs_price(spot, strike, years, rate, vol, opt),
            "Binomial (European)": european,
            "Binomial (American)": american,
            "Monte Carlo": mc.price,
            "MC 95% low": low,
            "MC 95% high": high,
            "Early exercise premium": american - european,
        }

    name = args.ticker.upper() if args.ticker else "Underlying"
    print(f"{name} | spot {spot:,.2f} | strike {strike:,.2f} | maturity {args.days} days")
    print(f"Rate {args.rate * 100:.1f}% | volatility {vol * 100:.1f}%")
    print(f"Binomial: {args.steps} steps | Monte Carlo: {args.paths:,} paths (antithetic)\n")
    print(pd.DataFrame(rows).T.round(3).to_string())


if __name__ == "__main__":
    main()
