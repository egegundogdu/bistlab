"""Fetches and stores fund price history from TEFAS."""

from __future__ import annotations

import argparse
import datetime as dt

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session
from tefas import Crawler

from bistlab.data.db import Fund, FundPrice, get_engine, init_db


def normalize_fund_prices(raw: pd.DataFrame) -> pd.DataFrame:
    """Reduces TEFAS output to a (date, price) table; drops zero prices and duplicate days."""
    if raw.empty:
        return pd.DataFrame(columns=["date", "price"])
    df = raw.rename(columns=str.lower)[["date", "price"]].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["price"] = df["price"].astype(float)
    df = df[df["price"] > 0]
    df = df.drop_duplicates("date", keep="last").sort_values("date")
    return df.reset_index(drop=True)


def fetch_fund_prices(code: str, start: dt.date, end: dt.date) -> pd.DataFrame:
    """Fetches daily fund prices from TEFAS (needs internet; at most 5 years)."""
    raw = Crawler().fetch(
        start=start.isoformat(),
        end=end.isoformat(),
        name=code.strip().upper(),
        columns=["code", "date", "price"],
    )
    return normalize_fund_prices(raw)


def get_or_create_fund(session: Session, code: str) -> Fund:
    """Finds the fund row or creates it."""
    code = code.strip().upper()
    fund = session.scalar(select(Fund).where(Fund.code == code))
    if fund is None:
        fund = Fund(code=code)
        session.add(fund)
        session.flush()
    return fund


def save_fund_prices(session: Session, code: str, prices: pd.DataFrame) -> int:
    """Upserts prices by day. Returns the number of rows written."""
    fund = get_or_create_fund(session, code)
    for record in prices.to_dict("records"):
        session.merge(FundPrice(fund_id=fund.id, date=record["date"], price=float(record["price"])))
    session.commit()
    return len(prices)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch TEFAS fund prices into the database.")
    parser.add_argument("codes", nargs="+", help="Fund codes, e.g. IKP")
    parser.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2023, 1, 1))
    args = parser.parse_args()

    engine = get_engine()
    init_db(engine)
    with Session(engine) as session:
        for code in args.codes:
            prices = fetch_fund_prices(code, args.start, dt.date.today())
            count = save_fund_prices(session, code, prices)
            if prices.empty:
                print(f"{code}: no data returned")
                continue
            first, last = prices.iloc[0], prices.iloc[-1]
            change = last["price"] / first["price"] - 1
            print(
                f"{code}: {count} days | {first['date']} {first['price']:.4f} → "
                f"{last['date']} {last['price']:.4f} | total {change * 100:.1f}%"
            )


if __name__ == "__main__":
    main()
