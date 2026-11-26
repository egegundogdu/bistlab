"""Merton / KMV yapısal kredi modeli.

Hisse, şirket varlıkları üzerine yazılmış bir call opsiyonudur (kullanım fiyatı = borç).
Piyasa değeri (E) ve hisse oynaklığından (σE) iki denklemle varlık değeri (V) ve
varlık oynaklığı (σV) çözülür:
    E    = V·N(d1) − D·e^(−rT)·N(d2)
    σE·E = N(d1)·σV·V
Temerrüde uzaklık DD = d2, risk-nötr temerrüt olasılığı PD = N(−DD).
KMV temerrüt noktası: kısa vadeli borç + uzun vadeli borcun yarısı.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pandas as pd
import yfinance as yf
from scipy.optimize import root
from scipy.stats import norm
from sqlalchemy.orm import Session

from bistlab.common import column
from bistlab.credit.scores import credit_table
from bistlab.data.db import get_engine
from bistlab.derivatives.black_scholes import d1_d2
from bistlab.funds.holding_prices import fetch_history, to_yahoo
from bistlab.portfolio.risk import annualized_volatility
from bistlab.valuation.beta import load_closes
from bistlab.valuation.report import load_items


@dataclass(frozen=True)
class MertonResult:
    asset_value: float
    asset_vol: float
    distance_to_default: float
    default_probability: float


def default_point(short_debt: float, long_debt: float) -> float:
    return short_debt + 0.5 * long_debt


def merton_equity(
    asset_value: float, asset_vol: float, debt: float, rate: float, years: float = 1.0
) -> tuple[float, float]:
    """Varlıklardan hisse değeri ve hisse oynaklığı."""
    d1, d2 = d1_d2(asset_value, debt, years, rate, asset_vol, 0.0)
    equity = asset_value * norm.cdf(d1) - debt * math.exp(-rate * years) * norm.cdf(d2)
    equity_vol = norm.cdf(d1) * asset_vol * asset_value / equity
    return float(equity), float(equity_vol)


def solve_merton(
    equity: float, equity_vol: float, debt: float, rate: float, years: float = 1.0
) -> MertonResult:
    """Hisse değeri ve oynaklığından varlık değeri/oynaklığını çözer."""

    def equations(x: npt.NDArray[np.float64]) -> list[float]:
        value, vol = float(x[0]), abs(float(x[1]))
        e, ev = merton_equity(value, vol, debt, rate, years)
        return [e / equity - 1, ev / equity_vol - 1]

    start = [equity + debt, equity_vol * equity / (equity + debt)]
    solution = root(equations, start)
    if not solution.success:
        raise ValueError(f"Merton denklemleri çözülemedi: {solution.message}")
    value, vol = float(solution.x[0]), abs(float(solution.x[1]))
    _, d2 = d1_d2(value, debt, years, rate, vol, 0.0)
    return MertonResult(value, vol, float(d2), float(norm.cdf(-d2)))


def latest_debt(items: pd.DataFrame) -> tuple[str, float, float]:
    """Son dönemin kısa ve uzun vadeli finansal borcu (kiralama dahil)."""
    total = column(items, "Total Debt").dropna()
    if total.empty:
        raise ValueError("Toplam borç kalemi yok")
    period = total.index[-1]
    short = column(items, "Current Debt And Capital Lease Obligation").fillna(
        column(items, "Current Debt")
    )
    short_value = float(short.get(period, 0.0))
    short_value = 0.0 if math.isnan(short_value) else short_value
    return str(period)[:10], short_value, float(total[period]) - short_value


def last_close(symbol: str) -> float:
    history = fetch_history(symbol, dt.date.today() - dt.timedelta(days=10))
    return float(history["close"].iloc[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Merton/KMV temerrüt olasılığı")
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--rate", type=float, default=0.40, help="Yıllık TL risksiz faiz")
    args = parser.parse_args()
    rate = math.log1p(args.rate)

    print(
        f"{'Hisse':<7}{'Dönem':>11}{'E (mr TL)':>11}{'DP (mr TL)':>12}{'σE':>7}{'σV':>7}"
        f"{'DD':>7}{'PD':>9}{'  Z′′ / not':>14}"
    )
    with Session(get_engine()) as session:
        for ticker in args.tickers:
            code = ticker.upper()
            try:
                items, currency = load_items(session, code)
                period, short, long = latest_debt(items)
                symbol = to_yahoo(code, "equity_tr") or code
                market_cap = float(yf.Ticker(symbol).info["marketCap"])
                fx = 1.0 if currency == "TRY" else last_close(f"{currency}TRY=X")
                debt = default_point(short, long) * fx
                closes = load_closes(session, code)
                returns = closes.iloc[-253:].pct_change().dropna()
                equity_vol = annualized_volatility(returns)
                result = solve_merton(market_cap, equity_vol, debt, rate)
            except (ValueError, KeyError) as error:
                print(f"{code:<7} atlandı: {error}")
                continue
            scores = credit_table(items)
            last = scores.iloc[-1] if not scores.empty else None
            label = f"{last['z']:.2f} / {last['rating']}" if last is not None else "-"
            print(
                f"{code:<7}{period:>11}{market_cap / 1e9:>11.1f}{debt / 1e9:>12.1f}"
                f"{equity_vol:>7.2f}{result.asset_vol:>7.2f}"
                f"{result.distance_to_default:>7.2f}{result.default_probability:>9.2e}"
                f"{label:>14}"
            )
    print("\nDP: KMV temerrüt noktası (kısa vadeli + uzun vadeli borcun yarısı), TL'ye çevrili.")
    print("σE: son 1 yıl günlük hisse oynaklığı. PD: 1 yıllık risk-nötr temerrüt olasılığı.")
    print("Eğitim amaçlı model çıktısıdır; kredi notu ya da yatırım tavsiyesi değildir.")


if __name__ == "__main__":
    main()
