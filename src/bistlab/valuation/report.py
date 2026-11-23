"""Bir şirketin finansal kalemlerini yükleyip oran tablosunu yazdırır."""

from __future__ import annotations

import argparse

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from bistlab.data.db import FinancialItem, Security, get_engine
from bistlab.valuation.ratios import compute_ratios


def load_items(session: Session, ticker: str, source: str = "yfinance") -> tuple[pd.DataFrame, str]:
    """Kalemleri geniş tabloya çevirir (satır: dönem sonu, sütun: kalem) ve para birimini döner."""
    code = ticker.strip().upper().removesuffix(".IS")
    query = (
        select(
            FinancialItem.period_end,
            FinancialItem.item,
            FinancialItem.value,
            FinancialItem.currency,
        )
        .join(Security, Security.id == FinancialItem.security_id)
        .where(Security.ticker == code, FinancialItem.source == source)
    )
    records = [tuple(row) for row in session.execute(query).all()]
    if not records:
        raise ValueError(f"{code} için finansal veri yok. Önce bistlab.data.financials çalıştır.")

    long = pd.DataFrame(records, columns=["period_end", "item", "value", "currency"])
    currencies = set(long["currency"])
    if len(currencies) != 1:
        raise ValueError(f"{code} için birden fazla para birimi var: {currencies}")

    wide = long.pivot_table(index="period_end", columns="item", values="value", aggfunc="last")
    return wide, str(currencies.pop())


def main() -> None:
    parser = argparse.ArgumentParser(description="Şirketin yıllık oran tablosunu yazdırır.")
    parser.add_argument("ticker", help="Hisse kodu, ör. ASELS")
    args = parser.parse_args()

    with Session(get_engine()) as session:
        items, currency = load_items(session, args.ticker)

    ratios = compute_ratios(items)
    print(f"{args.ticker.upper()} | raporlama para birimi: {currency}\n")
    print(ratios.T.round(3).to_string())


if __name__ == "__main__":
    main()
