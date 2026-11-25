"""Hisseler ve portföy için risk raporu."""

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
    """Tek bir getiri serisinin metrikleri (yüzde olarak)."""
    return {
        "Yıllık getiri %": annualized_return(returns) * 100,
        "Oynaklık %": annualized_volatility(returns) * 100,
        "Sharpe": sharpe_ratio(returns, risk_free),
        "Maks. düşüş %": max_drawdown(returns) * 100,
        "VaR tarihsel %": historical_var(returns, level) * 100,
        "VaR normal %": parametric_var(returns, level) * 100,
        "CVaR %": conditional_var(returns, level) * 100,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Hisse ve portföy risk raporu.")
    parser.add_argument("tickers", nargs="+", help="Hisse kodları, ör. THYAO ASELS BIMAS")
    parser.add_argument("--weights", nargs="+", type=float, help="Ağırlıklar (varsayılan eşit)")
    parser.add_argument("--years", type=int, default=2, help="Kaç yıllık veri (varsayılan 2)")
    parser.add_argument("--risk-free", type=float, default=0.0, help="Yıllık risksiz faiz")
    parser.add_argument("--level", type=float, default=0.95, help="VaR güven düzeyi")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers]
    weights = args.weights or [1 / len(tickers)] * len(tickers)

    with Session(get_engine()) as session:
        closes = pd.concat([load_closes(session, t) for t in tickers], axis=1, join="inner")
    cutoff = closes.index.max() - pd.Timedelta(days=365 * args.years)
    returns = daily_returns(closes[closes.index >= cutoff])

    rows = {t: risk_row(returns[t], args.risk_free, args.level) for t in tickers}
    rows["PORTFÖY"] = risk_row(portfolio_returns(returns, weights), args.risk_free, args.level)
    table = pd.DataFrame(rows).T

    start, end = returns.index.min().date(), returns.index.max().date()
    print(f"Dönem: {start} → {end} ({len(returns)} işlem günü), TL bazında nominal")
    print(f"Ağırlıklar: {dict(zip(tickers, [round(w, 3) for w in weights], strict=True))}")
    print(f"Risksiz faiz: %{args.risk_free * 100:.1f} | VaR/CVaR: %{args.level * 100:.0f}, 1 gün\n")
    print(table.round(2).to_string())


if __name__ == "__main__":
    main()
