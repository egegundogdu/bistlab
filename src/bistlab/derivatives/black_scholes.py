"""Black-Scholes-Merton option pricing, Greeks and implied volatility."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Literal

import pandas as pd
from sqlalchemy.orm import Session

from bistlab.data.db import get_engine
from bistlab.portfolio.risk import annualized_volatility
from bistlab.valuation.beta import load_closes

OptionType = Literal["call", "put"]
_N = NormalDist()


def _validate(spot: float, strike: float, years: float, vol: float) -> None:
    if spot <= 0 or strike <= 0:
        raise ValueError("Spot and strike must be positive.")
    if years < 0 or vol < 0:
        raise ValueError("Maturity and volatility cannot be negative.")


def d1_d2(
    spot: float, strike: float, years: float, rate: float, vol: float, dividend_yield: float
) -> tuple[float, float]:
    sqrt_t = math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate - dividend_yield + 0.5 * vol * vol) * years) / (
        vol * sqrt_t
    )
    return d1, d1 - vol * sqrt_t


def bs_price(
    spot: float,
    strike: float,
    years: float,
    rate: float,
    vol: float,
    option: OptionType = "call",
    dividend_yield: float = 0.0,
) -> float:
    """European option price. `rate` and `dividend_yield` are continuously compounded."""
    _validate(spot, strike, years, vol)
    discounted_spot = spot * math.exp(-dividend_yield * years)
    discounted_strike = strike * math.exp(-rate * years)
    if years == 0 or vol == 0:
        # No uncertainty: the option equals its discounted intrinsic value
        if option == "call":
            return max(discounted_spot - discounted_strike, 0.0)
        return max(discounted_strike - discounted_spot, 0.0)
    d1, d2 = d1_d2(spot, strike, years, rate, vol, dividend_yield)
    if option == "call":
        return discounted_spot * _N.cdf(d1) - discounted_strike * _N.cdf(d2)
    return discounted_strike * _N.cdf(-d2) - discounted_spot * _N.cdf(-d1)


@dataclass(frozen=True)
class Greeks:
    delta: float  # price change when spot rises by 1
    gamma: float  # delta change when spot rises by 1
    vega: float  # price change for a 1-point (1%) rise in vol
    theta: float  # price change after one calendar day
    rho: float  # price change for a 1-point (1%) rise in rates


def greeks(
    spot: float,
    strike: float,
    years: float,
    rate: float,
    vol: float,
    option: OptionType = "call",
    dividend_yield: float = 0.0,
) -> Greeks:
    """Analytical Greeks; maturity and volatility must be positive."""
    _validate(spot, strike, years, vol)
    if years == 0 or vol == 0:
        raise ValueError("Greeks require positive maturity and volatility.")
    d1, d2 = d1_d2(spot, strike, years, rate, vol, dividend_yield)
    q_disc = math.exp(-dividend_yield * years)
    r_disc = math.exp(-rate * years)
    pdf = _N.pdf(d1)
    sqrt_t = math.sqrt(years)

    gamma = q_disc * pdf / (spot * vol * sqrt_t)
    vega = spot * q_disc * pdf * sqrt_t
    decay = -spot * q_disc * pdf * vol / (2 * sqrt_t)
    if option == "call":
        delta = q_disc * _N.cdf(d1)
        theta = (
            decay
            - rate * strike * r_disc * _N.cdf(d2)
            + dividend_yield * spot * q_disc * _N.cdf(d1)
        )
        rho = strike * years * r_disc * _N.cdf(d2)
    else:
        delta = q_disc * (_N.cdf(d1) - 1)
        theta = (
            decay
            + rate * strike * r_disc * _N.cdf(-d2)
            - dividend_yield * spot * q_disc * _N.cdf(-d1)
        )
        rho = -strike * years * r_disc * _N.cdf(-d2)
    return Greeks(delta, gamma, vega / 100, theta / 365, rho / 100)


def implied_volatility(
    price: float,
    spot: float,
    strike: float,
    years: float,
    rate: float,
    option: OptionType = "call",
    dividend_yield: float = 0.0,
) -> float:
    """Volatility that reproduces the market price (bisection; price rises with volatility)."""
    low_price = bs_price(spot, strike, years, rate, 0.0, option, dividend_yield)
    if option == "call":
        high_price = spot * math.exp(-dividend_yield * years)
    else:
        high_price = strike * math.exp(-rate * years)
    if not low_price < price < high_price:
        raise ValueError(
            f"Price outside the no-arbitrage range ({low_price:.4f}, {high_price:.4f})."
        )
    low, high = 1e-6, 5.0
    for _ in range(200):
        mid = (low + high) / 2
        if bs_price(spot, strike, years, rate, mid, option, dividend_yield) < price:
            low = mid
        else:
            high = mid
        if high - low < 1e-10:
            break
    return (low + high) / 2


def main() -> None:
    parser = argparse.ArgumentParser(description="Black-Scholes option price and Greeks.")
    parser.add_argument(
        "--ticker", help="Underlying stock; last price and historical vol. come from it"
    )
    parser.add_argument("--spot", type=float, help="Underlying price (required without --ticker)")
    parser.add_argument("--strike", type=float, help="Strike (default: spot, ATM)")
    parser.add_argument("--days", type=int, default=30, help="Calendar days to maturity")
    parser.add_argument(
        "--rate", type=float, default=0.40, help="Annual risk-free rate (effective)"
    )
    parser.add_argument(
        "--vol", type=float, help="Annual volatility (historical when --ticker is given)"
    )
    parser.add_argument("--dividend-yield", type=float, default=0.0, help="Annual dividend yield")
    parser.add_argument("--type", choices=["call", "put"], default="call", help="Option type")
    args = parser.parse_args()

    spot, vol, vol_note = args.spot, args.vol, "given"
    if args.ticker:
        with Session(get_engine()) as session:
            closes = load_closes(session, args.ticker)
        spot = spot or float(closes.iloc[-1])
        if vol is None:
            last_year = closes.iloc[-253:]
            vol = annualized_volatility((last_year / last_year.shift(1) - 1).dropna())
            vol_note = "historical volatility, last year"
    if spot is None or vol is None:
        parser.error("give --ticker, or --spot and --vol.")

    strike = args.strike or spot
    years = args.days / 365
    rate = math.log1p(args.rate)  # effective annual → continuously compounded
    q = math.log1p(args.dividend_yield)
    option: OptionType = args.type

    price = bs_price(spot, strike, years, rate, vol, option, q)
    g = greeks(spot, strike, years, rate, vol, option, q)
    forward = spot * math.exp((rate - q) * years)

    name = args.ticker.upper() if args.ticker else "Underlying"
    print(f"{name} | spot {spot:,.2f} | strike {strike:,.2f} | maturity {args.days} days")
    print(f"Rate {args.rate * 100:.1f}% | volatility {vol * 100:.1f}% ({vol_note})")
    print(f"Forward price: {forward:,.2f}\n")
    print(f"{option.upper()} price: {price:,.4f}")
    print(
        f"Delta {g.delta:.4f} | Gamma {g.gamma:.5f} | Vega {g.vega:.4f} | "
        f"Theta/day {g.theta:.4f} | Rho {g.rho:.4f}"
    )

    rows = []
    for moneyness in (0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.20):
        k = spot * moneyness
        rows.append(
            {
                "Strike": k,
                "K / Spot": moneyness,
                "Call": bs_price(spot, k, years, rate, vol, "call", q),
                "Put": bs_price(spot, k, years, rate, vol, "put", q),
                "Call delta": greeks(spot, k, years, rate, vol, "call", q).delta,
            }
        )
    print("\nBy strike:")
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    print("\nModel assumptions: constant volatility, lognormal prices, European exercise.")


if __name__ == "__main__":
    main()
