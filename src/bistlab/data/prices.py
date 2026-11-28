"""Fetches BIST price data into the database."""

from __future__ import annotations

import argparse
import datetime as dt

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from bistlab.data.db import Price, get_engine, get_or_create_security, init_db

PRICE_COLUMNS = ["open", "high", "low", "close", "volume"]


def to_yahoo_symbol(ticker: str) -> str:
    """BIST ticker to Yahoo Finance symbol: THYAO -> THYAO.IS"""
    ticker = ticker.strip().upper()
    return ticker if ticker.endswith(".IS") else f"{ticker}.IS"


def normalize_prices(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalises raw data to: date, open, high, low, close, volume."""
    if raw.empty:
        return pd.DataFrame(columns=["date", *PRICE_COLUMNS])
    df = raw.rename(columns=str.lower)[PRICE_COLUMNS].copy()
    df = df.dropna(subset=["close"])
    df["volume"] = df["volume"].fillna(0).astype("int64")
    dates = pd.DatetimeIndex(df.index)
    df.insert(0, "date", dates.date)
    return df.reset_index(drop=True)


def fetch_prices(ticker: str, start: dt.date, end: dt.date | None = None) -> pd.DataFrame:
    """Fetches daily prices from Yahoo Finance (needs internet)."""
    raw = yf.Ticker(to_yahoo_symbol(ticker)).history(start=start, end=end, auto_adjust=True)
    return normalize_prices(raw)


def save_prices(session: Session, ticker: str, prices: pd.DataFrame) -> int:
    """Upserts prices by day. Returns the number of rows written."""
    security = get_or_create_security(session, ticker)

    fetched_at = dt.datetime.now(dt.UTC)
    for record in prices.to_dict("records"):
        session.merge(
            Price(
                security_id=security.id,
                date=record["date"],
                open=float(record["open"]),
                high=float(record["high"]),
                low=float(record["low"]),
                close=float(record["close"]),
                volume=int(record["volume"]),
                fetched_at=fetched_at,
            )
        )
    session.commit()
    return len(prices)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch BIST prices into the database.")
    parser.add_argument("tickers", nargs="+", help="Tickers, e.g. THYAO ASELS")
    parser.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2020, 1, 1))
    args = parser.parse_args()

    engine = get_engine()
    init_db(engine)
    with Session(engine) as session:
        for ticker in args.tickers:
            prices = fetch_prices(ticker, args.start)
            count = save_prices(session, ticker, prices)
            print(f"{ticker}: {count} days saved")


if __name__ == "__main__":
    main()
