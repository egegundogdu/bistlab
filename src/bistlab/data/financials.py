"""Fetches and stores financial statements (income, balance sheet, cash flow)."""

from __future__ import annotations

import argparse
import datetime as dt

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from bistlab.data.db import FinancialItem, get_engine, get_or_create_security, init_db
from bistlab.data.prices import to_yahoo_symbol

SOURCE = "yfinance"

# (period end, statement, line item, value)
FinancialRow = tuple[dt.date, str, str, float]


def to_long(table: pd.DataFrame, statement: str) -> list[FinancialRow]:
    """Converts yfinance's wide table (rows: items, columns: periods) to a long list."""
    rows: list[FinancialRow] = []
    for item, series in table.iterrows():
        for period, value in series.items():
            if pd.isna(value):
                continue
            period_end = pd.Timestamp(str(period)).date()
            rows.append((period_end, statement, str(item), float(value)))
    return rows


def fetch_financials(ticker: str) -> tuple[list[FinancialRow], str]:
    """Fetches annual statements and the reporting currency (needs internet)."""
    stock = yf.Ticker(to_yahoo_symbol(ticker))
    currency = stock.info.get("financialCurrency")
    if not currency:
        raise ValueError(f"No reporting currency found for {ticker}.")

    tables = {
        "income": stock.income_stmt,
        "balance": stock.balance_sheet,
        "cashflow": stock.cashflow,
    }
    rows: list[FinancialRow] = []
    for statement, table in tables.items():
        rows.extend(to_long(table, statement))
    return rows, str(currency)


def save_financials(
    session: Session, ticker: str, rows: list[FinancialRow], currency: str, source: str = SOURCE
) -> int:
    """Upserts line items. Returns the number of rows written."""
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
    parser = argparse.ArgumentParser(description="Fetch and store annual financial statements.")
    parser.add_argument("tickers", nargs="+", help="Tickers, e.g. THYAO ASELS")
    args = parser.parse_args()

    engine = get_engine()
    init_db(engine)
    with Session(engine) as session:
        for ticker in args.tickers:
            rows, currency = fetch_financials(ticker)
            count = save_financials(session, ticker, rows, currency)
            print(f"{ticker}: {count} items saved ({currency})")


if __name__ == "__main__":
    main()
