"""Varsayım dosyası ve veritabanı verisiyle uçtan uca DCF değerlemesi."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from bistlab.data.db import MacroObservation, get_engine
from bistlab.valuation import assumptions as assumptions_file
from bistlab.valuation.assumptions import Assumptions
from bistlab.valuation.beta import beta, load_closes, weekly_returns
from bistlab.valuation.dcf import (
    blume_adjust,
    capm_cost_of_equity,
    convert_rate,
    dcf_value,
    sensitivity_table,
    wacc,
)
from bistlab.valuation.report import load_items

USD_TRY = "TP.DK.USD.A.YTL"
MARKET_INDEX = "XU100"


def latest(items: pd.DataFrame, name: str) -> float:
    """Kalemin en son dolu değeri."""
    return average_last(items, name, 1)


def average_last(items: pd.DataFrame, name: str, years: int) -> float:
    """Kalemin son `years` yıldaki dolu değerlerinin ortalaması."""
    if name not in items.columns:
        raise ValueError(f"'{name}' kalemi bulunamadı.")
    series = items[name].dropna().sort_index().tail(years)
    if series.empty:
        raise ValueError(f"'{name}' kalemi boş.")
    return float(series.mean())


def project_cash_flows(base: float, growth: Sequence[float]) -> list[float]:
    """Baz nakit akışını yıllık büyüme oranlarıyla ileriye taşır."""
    flows: list[float] = []
    value = base
    for g in growth:
        value *= 1 + g
        flows.append(value)
    return flows


def cost_of_capital(
    a: Assumptions, equity_value: float, debt_value: float, beta_value: float
) -> tuple[float, float]:
    """(özkaynak maliyeti, WACC), raporlama para biriminde.

    Özkaynak maliyeti önce USD bazlı CAPM ile bulunur; şirket TL raporluyorsa
    enflasyon farkıyla TL'ye çevrilir.
    """
    ke_usd = capm_cost_of_equity(a.usd_risk_free, beta_value, a.equity_risk_premium)
    if a.currency == "USD":
        ke = ke_usd
    else:
        ke = convert_rate(ke_usd, a.us_inflation, a.local_inflation)
    return ke, wacc(equity_value, debt_value, ke, a.pre_tax_cost_of_debt, a.tax_rate)


def terminal_growth(a: Assumptions) -> float:
    """Nominal terminal büyüme = (1 + reel büyüme) × (1 + uzun vadeli enflasyon) - 1."""
    inflation = a.us_inflation if a.currency == "USD" else a.local_inflation
    return (1 + a.terminal_real_growth) * (1 + inflation) - 1


def latest_macro(session: Session, code: str) -> float:
    """Bir makro serinin en son değeri."""
    query = (
        select(MacroObservation.value)
        .where(MacroObservation.code == code)
        .order_by(MacroObservation.date.desc())
        .limit(1)
    )
    value = session.scalar(query)
    if value is None:
        raise ValueError(f"{code} için veri yok. Önce bistlab.data.evds çalıştır.")
    return float(value)


def _bn(value: float) -> str:
    return f"{value / 1e9:,.1f} mr"


def main() -> None:
    parser = argparse.ArgumentParser(description="Varsayım dosyasıyla DCF değerlemesi yapar.")
    parser.add_argument("ticker", help="Hisse kodu; assumptions/<KOD>.toml olmalı")
    args = parser.parse_args()

    a = assumptions_file.load(args.ticker)
    with Session(get_engine()) as session:
        items, currency = load_items(session, a.ticker)
        closes = load_closes(session, a.ticker)
        market = load_closes(session, MARKET_INDEX)
        usd_try = latest_macro(session, USD_TRY)
    if currency != a.currency:
        raise ValueError(f"Varsayım dosyası {a.currency}, veritabanı {currency} diyor.")

    cutoff = closes.index.max() - pd.Timedelta(days=730)
    raw_beta = beta(
        weekly_returns(closes[closes.index >= cutoff]),
        weekly_returns(market[market.index >= cutoff]),
    )
    if a.beta_override is not None:
        beta_value, beta_note = a.beta_override, "elle girildi"
    elif a.use_blume:
        beta_value, beta_note = blume_adjust(raw_beta), "Blume düzeltmeli"
    else:
        beta_value, beta_note = raw_beta, "ham"

    to_try = 1.0 if a.currency == "TRY" else usd_try
    price_try = float(closes.iloc[-1])
    shares = latest(items, "Ordinary Shares Number")
    market_cap = price_try * shares / to_try
    total_debt = latest(items, "Total Debt")
    net_debt = total_debt - latest(items, "Cash And Cash Equivalents")
    base_fcf = average_last(items, "Free Cash Flow", a.base_fcf_years)

    ke, rate = cost_of_capital(a, market_cap, total_debt, beta_value)
    g = terminal_growth(a)
    flows = project_cash_flows(base_fcf, a.growth)
    result = dcf_value(flows, rate, g, net_debt, shares)
    value_try = result.per_share * to_try
    cur = a.currency

    print(f"{a.ticker} | raporlama para birimi: {cur}\n")
    print(f"Beta: ham {raw_beta:.2f} → kullanılan {beta_value:.2f} ({beta_note})")
    print(f"Özkaynak maliyeti: {ke:.1%} | WACC: {rate:.1%} | Terminal büyüme: {g:.1%}")
    print(f"Baz FCF (son {a.base_fcf_years} yıl ort.): {_bn(base_fcf)} {cur}")
    print(f"Firma değeri: {_bn(result.enterprise_value)} {cur} | Net borç: {_bn(net_debt)} {cur}")
    print(f"Terminal değerin payı: {result.terminal_share:.0%}")
    print(f"\nHisse başı değer: {value_try:,.2f} TL | Son fiyat: {price_try:,.2f} TL", end="")
    print(f" | Fark: {value_try / price_try - 1:+.0%}")

    rates = [rate + d for d in (-0.02, -0.01, 0.0, 0.01, 0.02)]
    growths = [g + d for d in (-0.01, 0.0, 0.01)]
    table = sensitivity_table(flows, net_debt, shares, rates, growths) * to_try
    table.index = [f"WACC {r:.1%}" for r in rates]
    table.columns = [f"g {x:.1%}" for x in growths]
    print("\nDuyarlılık (TL / hisse):")
    print(table.round(2).to_string())
    print("\nEğitim amaçlıdır; yatırım tavsiyesi değildir.")


if __name__ == "__main__":
    main()
