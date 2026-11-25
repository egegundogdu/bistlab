"""Aynı opsiyonu Black-Scholes, binom ağacı ve Monte Carlo ile fiyatlayıp karşılaştırır."""

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
    parser = argparse.ArgumentParser(description="Üç yöntemle opsiyon fiyatı karşılaştırması.")
    parser.add_argument("--ticker", help="Dayanak hisse; son fiyat ve tarihsel vol. buradan")
    parser.add_argument("--spot", type=float, help="Dayanak fiyatı (ticker yoksa zorunlu)")
    parser.add_argument("--strike", type=float, help="Kullanım fiyatı (varsayılan: spot)")
    parser.add_argument("--days", type=int, default=180, help="Vadeye kalan takvim günü")
    parser.add_argument("--rate", type=float, default=0.40, help="Yıllık risksiz faiz (efektif)")
    parser.add_argument("--vol", type=float, help="Yıllık volatilite (ticker varsa tarihsel)")
    parser.add_argument("--steps", type=int, default=1000, help="Binom ağacı adım sayısı")
    parser.add_argument("--paths", type=int, default=200_000, help="Monte Carlo yol sayısı")
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
        parser.error("--ticker ya da --spot ve --vol verilmeli.")

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
            "Binom (Avrupa)": european,
            "Binom (Amerikan)": american,
            "Monte Carlo": mc.price,
            "MC %95 alt": low,
            "MC %95 üst": high,
            "Erken kullanım primi": american - european,
        }

    name = args.ticker.upper() if args.ticker else "Dayanak"
    print(f"{name} | spot {spot:,.2f} | kullanım {strike:,.2f} | vade {args.days} gün")
    print(f"Faiz %{args.rate * 100:.1f} | volatilite %{vol * 100:.1f}")
    print(f"Binom: {args.steps} adım | Monte Carlo: {args.paths:,} yol (karşıt değişkenli)\n")
    print(pd.DataFrame(rows).T.round(3).to_string())


if __name__ == "__main__":
    main()
