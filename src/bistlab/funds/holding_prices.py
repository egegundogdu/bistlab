"""Fetches price history for the stocks held by a fund (for look-through analysis)."""

from __future__ import annotations

import argparse
import datetime as dt

import pandas as pd
import yfinance as yf
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bistlab.data.db import (
    Fund,
    FundHolding,
    Price,
    get_engine,
    get_or_create_security,
    init_db,
)

# Bloomberg exchange code -> Yahoo Finance suffix
EXCHANGE_SUFFIX = {
    "US": "",
    "GY": ".DE",
    "GR": ".DE",
    "FP": ".PA",
    "SM": ".MC",
    "IM": ".MI",
    "NA": ".AS",
    "AV": ".VI",
    "FH": ".HE",
    "LN": ".L",
    "PL": ".LS",
    "JT": ".T",
}
COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def to_yahoo(asset: str, asset_type: str) -> str | None:
    """'SAHOL' -> 'SAHOL.IS', 'ENR GY' -> 'ENR.DE'. None if not a stock."""
    if asset_type == "equity_tr":
        return f"{asset}.IS"
    if asset_type != "equity_foreign":
        return None
    parts = asset.split()
    if len(parts) != 2 or parts[1] not in EXCHANGE_SUFFIX:
        return None
    return parts[0] + EXCHANGE_SUFFIX[parts[1]]


def storage_ticker(symbol: str) -> str:
    """BIST stocks are stored without a suffix (e.g. THYAO)."""
    return symbol.removesuffix(".IS")


def normalize_history(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=COLUMNS)
    df = raw.rename(columns=str.lower)[COLUMNS[1:]].copy()
    index = pd.DatetimeIndex(df.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    df.insert(0, "date", index.date)
    df = df.dropna(subset=["close"])
    df = df[df["close"] > 0]
    df["volume"] = df["volume"].fillna(0)
    return df.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)


def fetch_history(symbol: str, start: dt.date) -> pd.DataFrame:
    raw = yf.Ticker(symbol).history(start=start.isoformat(), auto_adjust=True)
    return normalize_history(raw)


def latest_holdings(session: Session, fund_code: str) -> list[FundHolding]:
    fund = session.scalars(select(Fund).where(Fund.code == fund_code)).one()
    last = session.scalar(
        select(func.max(FundHolding.report_date)).where(FundHolding.fund_id == fund.id)
    )
    query = select(FundHolding).where(
        FundHolding.fund_id == fund.id, FundHolding.report_date == last
    )
    return list(session.scalars(query))


def save_history(session: Session, ticker: str, history: pd.DataFrame) -> int:
    security = get_or_create_security(session, ticker)
    fetched_at = dt.datetime.now(dt.UTC)
    for row in history.to_dict("records"):
        session.merge(
            Price(
                security_id=security.id,
                date=row["date"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
                fetched_at=fetched_at,
            )
        )
    return len(history)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch prices for the stocks in a fund")
    parser.add_argument("fund")
    parser.add_argument("--start", default="2023-01-01")
    args = parser.parse_args()
    start = dt.date.fromisoformat(args.start)

    engine = get_engine()
    init_db(engine)
    covered = total = 0.0
    missing: list[str] = []
    with Session(engine) as session:
        holdings = latest_holdings(session, args.fund.upper())
        for holding in holdings:
            symbol = to_yahoo(holding.asset, holding.asset_type)
            if holding.asset_type.startswith("equity"):
                total += holding.weight
            if symbol is None:
                if holding.asset_type.startswith("equity"):
                    missing.append(f"{holding.asset} (no mapping)")
                continue
            try:
                history = fetch_history(symbol, start)
            except Exception as error:  # yfinance sometimes raises
                missing.append(f"{symbol} ({type(error).__name__})")
                continue
            if history.empty:
                missing.append(f"{symbol} (no data)")
                continue
            days = save_history(session, storage_ticker(symbol), history)
            session.commit()
            covered += holding.weight
            print(f"{symbol:<10} {days:>4} days  weight {holding.weight * 100:5.2f}%")

    print(f"\nStock weight: {total * 100:.2f}%, with prices: {covered * 100:.2f}%")
    if missing:
        print("Missing:", ", ".join(missing))


if __name__ == "__main__":
    main()
