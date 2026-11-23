"""Finansal tabloları (gelir tablosu, bilanço, nakit akışı) çekme ve saklama."""

from __future__ import annotations

import argparse
import datetime as dt

import pandas as pd
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.orm import Session

from bistlab.data.db import FinancialItem, Security, get_engine, init_db
from bistlab.data.prices import to_yahoo_symbol

SOURCE = "yfinance"

# (dönem sonu, tablo türü, kalem adı, değer)
FinancialRow = tuple[dt.date, str, str, float]


def to_long(table: pd.DataFrame, statement: str) -> list[FinancialRow]:
    """yfinance'in geniş tablosunu (satır: kalem, sütun: dönem) uzun listeye çevirir."""
    rows: list[FinancialRow] = []
    for item, series in table.iterrows():
        for period, value in series.items():
            if pd.isna(value):
                continue
            period_end = pd.Timestamp(str(period)).date()
            rows.append((period_end, statement, str(item), float(value)))
    return rows


def fetch_financials(ticker: str) -> tuple[list[FinancialRow], str]:
    """Yıllık tabloları ve raporlama para birimini çeker (internet gerekir)."""
    stock = yf.Ticker(to_yahoo_symbol(ticker))
    currency = stock.info.get("financialCurrency")
    if not currency:
        raise ValueError(f"{ticker} için raporlama para birimi bulunamadı.")

    tables = {
        "income": stock.income_stmt,
        "balance": stock.balance_sheet,
        "cashflow": stock.cashflow,
    }
    rows: list[FinancialRow] = []
    for statement, table in tables.items():
        rows.extend(to_long(table, statement))
    return rows, str(currency)


def get_or_create_security(session: Session, ticker: str) -> Security:
    """Hisse kaydını bulur; yoksa oluşturur."""
    code = ticker.strip().upper().removesuffix(".IS")
    security = session.scalar(select(Security).where(Security.ticker == code))
    if security is None:
        security = Security(ticker=code)
        session.add(security)
        session.flush()
    return security


def save_financials(
    session: Session, ticker: str, rows: list[FinancialRow], currency: str, source: str = SOURCE
) -> int:
    """Kalemleri yazar; aynı kayıt varsa günceller. Yazılan satır sayısını döner."""
    security = get_or_create_security(session, ticker)
    for period_end, statement, item, value in rows:
        session.merge(
            FinancialItem(
                security_id=security.id,
                period_end=period_end,
                statement=statement,
                item=item,
                source=source,
                value=value,
                currency=currency,
            )
        )
    session.commit()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Yıllık finansal tabloları çekip kaydeder.")
    parser.add_argument("tickers", nargs="+", help="Hisse kodları, ör. THYAO ASELS")
    args = parser.parse_args()

    engine = get_engine()
    init_db(engine)
    with Session(engine) as session:
        for ticker in args.tickers:
            rows, currency = fetch_financials(ticker)
            count = save_financials(session, ticker, rows, currency)
            print(f"{ticker}: {count} kalem kaydedildi ({currency})")


if __name__ == "__main__":
    main()
