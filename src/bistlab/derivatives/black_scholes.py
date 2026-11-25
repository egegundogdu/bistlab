"""Black-Scholes-Merton opsiyon fiyatlama, Greeks ve ima edilen volatilite."""

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
        raise ValueError("Spot ve kullanım fiyatı pozitif olmalı.")
    if years < 0 or vol < 0:
        raise ValueError("Vade ve volatilite negatif olamaz.")


def _d1_d2(
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
    """Avrupa tipi opsiyon fiyatı. `rate` ve `dividend_yield` sürekli bileşik oranlardır."""
    _validate(spot, strike, years, vol)
    discounted_spot = spot * math.exp(-dividend_yield * years)
    discounted_strike = strike * math.exp(-rate * years)
    if years == 0 or vol == 0:
        # Belirsizlik yok: opsiyon, iskonto edilmiş içsel değerine eşittir
        if option == "call":
            return max(discounted_spot - discounted_strike, 0.0)
        return max(discounted_strike - discounted_spot, 0.0)
    d1, d2 = _d1_d2(spot, strike, years, rate, vol, dividend_yield)
    if option == "call":
        return discounted_spot * _N.cdf(d1) - discounted_strike * _N.cdf(d2)
    return discounted_strike * _N.cdf(-d2) - discounted_spot * _N.cdf(-d1)


@dataclass(frozen=True)
class Greeks:
    delta: float  # spot 1 TL artınca fiyat değişimi
    gamma: float  # spot 1 TL artınca delta değişimi
    vega: float  # volatilite 1 puan (%1) artınca fiyat değişimi
    theta: float  # 1 takvim günü geçince fiyat değişimi
    rho: float  # faiz 1 puan (%1) artınca fiyat değişimi


def greeks(
    spot: float,
    strike: float,
    years: float,
    rate: float,
    vol: float,
    option: OptionType = "call",
    dividend_yield: float = 0.0,
) -> Greeks:
    """Analitik Greeks; vade ve volatilite pozitif olmalı."""
    _validate(spot, strike, years, vol)
    if years == 0 or vol == 0:
        raise ValueError("Greeks için vade ve volatilite pozitif olmalı.")
    d1, d2 = _d1_d2(spot, strike, years, rate, vol, dividend_yield)
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
    """Piyasa fiyatını veren volatilite (ikiye bölme; fiyat volatiliteyle monoton artar)."""
    low_price = bs_price(spot, strike, years, rate, 0.0, option, dividend_yield)
    if option == "call":
        high_price = spot * math.exp(-dividend_yield * years)
    else:
        high_price = strike * math.exp(-rate * years)
    if not low_price < price < high_price:
        raise ValueError(
            f"Fiyat arbitrajsız aralıkta değil: ({low_price:.4f}, {high_price:.4f}) olmalı."
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
    parser = argparse.ArgumentParser(description="Black-Scholes opsiyon fiyatı ve Greeks.")
    parser.add_argument("--ticker", help="Dayanak hisse; son fiyat ve tarihsel vol. buradan")
    parser.add_argument("--spot", type=float, help="Dayanak fiyatı (ticker yoksa zorunlu)")
    parser.add_argument("--strike", type=float, help="Kullanım fiyatı (varsayılan: spot, ATM)")
    parser.add_argument("--days", type=int, default=30, help="Vadeye kalan takvim günü")
    parser.add_argument("--rate", type=float, default=0.40, help="Yıllık risksiz faiz (efektif)")
    parser.add_argument("--vol", type=float, help="Yıllık volatilite (ticker varsa tarihsel)")
    parser.add_argument("--dividend-yield", type=float, default=0.0, help="Yıllık temettü verimi")
    parser.add_argument("--type", choices=["call", "put"], default="call", help="Opsiyon türü")
    args = parser.parse_args()

    spot, vol, vol_note = args.spot, args.vol, "girildi"
    if args.ticker:
        with Session(get_engine()) as session:
            closes = load_closes(session, args.ticker)
        spot = spot or float(closes.iloc[-1])
        if vol is None:
            last_year = closes.iloc[-253:]
            vol = annualized_volatility((last_year / last_year.shift(1) - 1).dropna())
            vol_note = "son 1 yılın tarihsel volatilitesi"
    if spot is None or vol is None:
        parser.error("--ticker ya da --spot ve --vol verilmeli.")

    strike = args.strike or spot
    years = args.days / 365
    rate = math.log1p(args.rate)  # efektif yıllık → sürekli bileşik
    q = math.log1p(args.dividend_yield)
    option: OptionType = args.type

    price = bs_price(spot, strike, years, rate, vol, option, q)
    g = greeks(spot, strike, years, rate, vol, option, q)
    forward = spot * math.exp((rate - q) * years)

    name = args.ticker.upper() if args.ticker else "Dayanak"
    print(f"{name} | spot {spot:,.2f} | kullanım {strike:,.2f} | vade {args.days} gün")
    print(f"Faiz %{args.rate * 100:.1f} | volatilite %{vol * 100:.1f} ({vol_note})")
    print(f"Vadeli (forward) fiyat: {forward:,.2f}\n")
    print(f"{option.upper()} fiyatı: {price:,.4f}")
    print(
        f"Delta {g.delta:.4f} | Gamma {g.gamma:.5f} | Vega {g.vega:.4f} | "
        f"Theta/gün {g.theta:.4f} | Rho {g.rho:.4f}"
    )

    rows = []
    for moneyness in (0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.20):
        k = spot * moneyness
        rows.append(
            {
                "Kullanım": k,
                "K / Spot": moneyness,
                "Call": bs_price(spot, k, years, rate, vol, "call", q),
                "Put": bs_price(spot, k, years, rate, vol, "put", q),
                "Call delta": greeks(spot, k, years, rate, vol, "call", q).delta,
            }
        )
    print("\nKullanım fiyatına göre:")
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    print("\nModel varsayımları: sabit volatilite, lognormal fiyat, Avrupa tipi kullanım.")


if __name__ == "__main__":
    main()
