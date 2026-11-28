"""Vadeli işlemler: taşıma maliyeti modeli, baz ve minimum varyanslı hedge."""

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
    """Taşıma maliyeti modeli: F = S × ((1 + r) / (1 + q))^T; r ve q yıllık efektif oranlar."""
    _check_years(years)
    return spot * float(((1 + rate) / (1 + dividend_yield)) ** years)


def implied_rate(futures: float, spot: float, years: float, dividend_yield: float = 0.0) -> float:
    """Vadeli fiyatın ima ettiği yıllık efektif finansman oranı."""
    _check_years(years)
    return float((futures / spot) ** (1 / years)) * (1 + dividend_yield) - 1


@dataclass(frozen=True)
class HedgeResult:
    ratio: float  # varlığın 1 TL'si için satılacak vadeli nominali
    unhedged_vol: float
    hedged_vol: float

    @property
    def risk_reduction(self) -> float:
        """Oynaklıktaki oransal azalma."""
        return 1 - self.hedged_vol / self.unhedged_vol


def min_variance_hedge(
    asset_returns: pd.Series[float], hedge_returns: pd.Series[float]
) -> HedgeResult:
    """Minimum varyanslı hedge oranı = Kov / Var, yani varlığın hedge aracına göre betası."""
    joined = pd.concat([asset_returns, hedge_returns], axis=1, join="inner").dropna()
    asset, hedge = joined.iloc[:, 0], joined.iloc[:, 1]
    ratio = beta(asset, hedge)
    hedged = asset - ratio * hedge
    scale = math.sqrt(TRADING_DAYS)
    return HedgeResult(ratio, float(asset.std(ddof=1)) * scale, float(hedged.std(ddof=1)) * scale)


def contracts_needed(notional: float, futures_price: float, multiplier: float) -> float:
    """Gereken kontrat sayısı = hedge nominali / (vadeli fiyat × kontrat çarpanı)."""
    if futures_price <= 0 or multiplier <= 0:
        raise ValueError("Futures price and contract multiplier must be positive.")
    return notional / (futures_price * multiplier)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hisse portföyünü endeks vadeliyle hedge eder.")
    parser.add_argument("tickers", nargs="+", help="Portföydeki hisseler (eşit ağırlık)")
    parser.add_argument("--value", type=float, default=1_000_000, help="Portföy değeri (TL)")
    parser.add_argument("--index", default="XU030", help="Vadelinin dayanak endeksi")
    parser.add_argument("--days", type=int, default=60, help="Calendar days to maturity")
    parser.add_argument("--rate", type=float, default=0.40, help="Annual effective interest rate")
    parser.add_argument("--dividend-yield", type=float, default=0.0, help="Endeks temettü verimi")
    parser.add_argument("--years", type=int, default=1, help="Hedge oranı için kaç yıl veri")
    parser.add_argument("--multiplier", type=float, help="Kontrat çarpanı (VİOP'tan kontrol et)")
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

    print(f"Portföy: {', '.join(tickers)} (eşit ağırlık) | değer {args.value:,.0f} TL")
    print(f"{index} spot: {spot:,.2f} | vade {args.days} gün | faiz %{args.rate * 100:.1f}\n")
    print(f"Teorik vadeli fiyat: {futures:,.2f}")
    print(f"Baz (F - S): {futures - spot:,.2f} puan (%{(futures / spot - 1) * 100:.2f})")
    print(f"Kontrol: ima edilen oran %{implied_rate(futures, spot, years) * 100:.1f}\n")
    print(f"Hedge oranı (beta, son {args.years} yıl, günlük): {hedge.ratio:.3f}")
    print(f"Satılacak vadeli nominali: {notional:,.0f} TL")
    if args.multiplier:
        count = contracts_needed(notional, futures, args.multiplier)
        print(f"Gereken kontrat: {count:,.1f} → yuvarlanmış {round(count)} adet")
    print(f"\nOynaklık (yıllık): hedgesiz %{hedge.unhedged_vol * 100:.1f}", end="")
    print(f" → hedgeli %{hedge.hedged_vol * 100:.1f} (azalma %{hedge.risk_reduction * 100:.0f})")
    print("\nNot: Vadeli fiyat teorik; gerçek piyasa fiyatı bazdan dolayı farklı olabilir.")
    print("Hedge sonrası kalan risk, portföyün endeksten bağımsız (şirkete özgü) riskidir.")


if __name__ == "__main__":
    main()
