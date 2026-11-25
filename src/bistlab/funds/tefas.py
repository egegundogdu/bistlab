"""TEFAS'tan fon fiyat geçmişi çekme ve saklama."""

from __future__ import annotations

import argparse
import datetime as dt

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session
from tefas import Crawler

from bistlab.data.db import Fund, FundPrice, get_engine, init_db


def normalize_fund_prices(raw: pd.DataFrame) -> pd.DataFrame:
    """TEFAS çıktısını (date, price) tablosuna indirger; sıfır fiyatı ve yinelenen günü ayıklar."""
    if raw.empty:
        return pd.DataFrame(columns=["date", "price"])
    df = raw.rename(columns=str.lower)[["date", "price"]].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["price"] = df["price"].astype(float)
    df = df[df["price"] > 0]
    df = df.drop_duplicates("date", keep="last").sort_values("date")
    return df.reset_index(drop=True)


def fetch_fund_prices(code: str, start: dt.date, end: dt.date) -> pd.DataFrame:
    """Bir fonun günlük fiyatlarını TEFAS'tan çeker (internet gerekir; en fazla 5 yıl)."""
    raw = Crawler().fetch(
        start=start.isoformat(),
        end=end.isoformat(),
        name=code.strip().upper(),
        columns=["code", "date", "price"],
    )
    return normalize_fund_prices(raw)


def get_or_create_fund(session: Session, code: str) -> Fund:
    """Fon kaydını bulur; yoksa oluşturur."""
    code = code.strip().upper()
    fund = session.scalar(select(Fund).where(Fund.code == code))
    if fund is None:
        fund = Fund(code=code)
        session.add(fund)
        session.flush()
    return fund


def save_fund_prices(session: Session, code: str, prices: pd.DataFrame) -> int:
    """Fiyatları yazar; aynı gün varsa günceller. Yazılan satır sayısını döner."""
    fund = get_or_create_fund(session, code)
    for record in prices.to_dict("records"):
        session.merge(FundPrice(fund_id=fund.id, date=record["date"], price=float(record["price"])))
    session.commit()
    return len(prices)


def main() -> None:
    parser = argparse.ArgumentParser(description="TEFAS fon fiyatlarını çekip veritabanına yazar.")
    parser.add_argument("codes", nargs="+", help="Fon kodları, ör. IKP")
    parser.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2023, 1, 1))
    args = parser.parse_args()

    engine = get_engine()
    init_db(engine)
    with Session(engine) as session:
        for code in args.codes:
            prices = fetch_fund_prices(code, args.start, dt.date.today())
            count = save_fund_prices(session, code, prices)
            if prices.empty:
                print(f"{code}: veri gelmedi")
                continue
            first, last = prices.iloc[0], prices.iloc[-1]
            change = last["price"] / first["price"] - 1
            print(
                f"{code}: {count} gün | {first['date']} {first['price']:.4f} → "
                f"{last['date']} {last['price']:.4f} | toplam %{change * 100:.1f}"
            )


if __name__ == "__main__":
    main()
