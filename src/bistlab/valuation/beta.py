"""Hisse betası: piyasa endeksine göre sistematik risk."""

from __future__ import annotations

import argparse
import datetime as dt

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from bistlab.data.db import Price, Security, get_engine

MIN_OBSERVATIONS = 20


def weekly_returns(closes: pd.Series[float]) -> pd.Series[float]:
    """Günlük kapanışlardan haftalık (Cuma kapanışı) basit getiriler."""
    weekly = closes.resample("W-FRI").last()
    return (weekly / weekly.shift(1) - 1).dropna()


def beta(stock_returns: pd.Series[float], market_returns: pd.Series[float]) -> float:
    """Beta = Kov(hisse, piyasa) / Var(piyasa). Sadece iki seride de olan tarihler kullanılır."""
    joined = pd.concat([stock_returns, market_returns], axis=1, join="inner").dropna()
    if len(joined) < MIN_OBSERVATIONS:
        raise ValueError(f"Beta için en az {MIN_OBSERVATIONS} ortak gözlem gerekli.")
    covariance = np.cov(joined.iloc[:, 0], joined.iloc[:, 1], ddof=1)
    return float(covariance[0, 1] / covariance[1, 1])


def load_closes(session: Session, ticker: str) -> pd.Series[float]:
    """Veritabanından bir hissenin günlük kapanış serisini okur."""
    code = ticker.strip().upper().removesuffix(".IS")
    query = (
        select(Price.date, Price.close)
        .join(Security, Security.id == Price.security_id)
        .where(Security.ticker == code)
        .order_by(Price.date)
    )
    rows = session.execute(query).all()
    if not rows:
        raise ValueError(f"{code} için fiyat verisi yok. Önce bistlab.data.prices çalıştır.")
    index = pd.DatetimeIndex([row[0] for row in rows])
    return pd.Series([row[1] for row in rows], index=index, dtype=float, name=code)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hissenin piyasaya göre betasını hesaplar.")
    parser.add_argument("ticker", help="Hisse kodu, ör. ASELS")
    parser.add_argument("--market", default="XU100", help="Piyasa endeksi (varsayılan XU100)")
    parser.add_argument("--years", type=int, default=2, help="Kaç yıllık veri (varsayılan 2)")
    args = parser.parse_args()

    cutoff = pd.Timestamp(dt.date.today() - dt.timedelta(days=365 * args.years))
    with Session(get_engine()) as session:
        stock = load_closes(session, args.ticker)
        market = load_closes(session, args.market)

    stock_r = weekly_returns(stock[stock.index >= cutoff])
    market_r = weekly_returns(market[market.index >= cutoff])
    value = beta(stock_r, market_r)
    weeks = len(pd.concat([stock_r, market_r], axis=1, join="inner").dropna())
    print(f"{args.ticker.upper()} betası ({args.market}, haftalık, {weeks} hafta): {value:.2f}")


if __name__ == "__main__":
    main()
