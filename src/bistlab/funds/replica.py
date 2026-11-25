"""Getiri farkı: fonun gerçek getirisi ile rapordaki varlıklardan kurulan kopya portföy.

Rapor tarihindeki varlıklar ay boyunca hiç değişmeseydi fon ne kazanırdı? Fark; ay içi
alım-satım kararlarını, işlem maliyetlerini ve yönetim ücretini birlikte gösterir.
"""

from __future__ import annotations

import argparse
import datetime as dt
from bisect import bisect_right
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from bistlab.data.db import Fund, FundPrice, Price, Security, get_engine
from bistlab.funds.holding_prices import fetch_history, latest_holdings, storage_ticker, to_yahoo

Series = list[tuple[dt.date, float]]


@dataclass(frozen=True)
class Position:
    asset: str
    weight: float
    tl_return: float | None  # None: fiyat verisi yok


@dataclass(frozen=True)
class ReplicaResult:
    portfolio_return: float
    covered_weight: float
    contributions: list[tuple[str, float]]


def value_on(series: Series, day: dt.date) -> float | None:
    """O gün ya da öncesindeki son değer."""
    index = bisect_right([date for date, _ in series], day)
    return None if index == 0 else series[index - 1][1]


def period_return(series: Series, start: dt.date, end: dt.date) -> float | None:
    first, last = value_on(series, start), value_on(series, end)
    if first is None or last is None or first <= 0:
        return None
    return last / first - 1


def to_tl(local_return: float, fx_return: float) -> float:
    return (1 + local_return) * (1 + fx_return) - 1


def cash_return(annual_rate: float, days: int) -> float:
    return float((1 + annual_rate) ** (days / 365) - 1)


def replica_return(positions: list[Position]) -> ReplicaResult:
    """Verisi olan varlıkların ağırlıklarını 1'e ölçekleyip getiriyi hesaplar."""
    known = [p for p in positions if p.tl_return is not None]
    covered = sum(p.weight for p in known)
    if covered <= 0:
        raise ValueError("Getirisi hesaplanabilen varlık yok")
    contributions = [(p.asset, p.weight * (p.tl_return or 0.0) / covered) for p in known]
    contributions.sort(key=lambda item: item[1])
    total_weight = sum(p.weight for p in positions)
    return ReplicaResult(
        portfolio_return=sum(c for _, c in contributions),
        covered_weight=covered / total_weight,
        contributions=contributions,
    )


def load_closes(session: Session, ticker: str) -> Series:
    query = (
        select(Price.date, Price.close)
        .join(Security, Security.id == Price.security_id)
        .where(Security.ticker == ticker)
        .order_by(Price.date)
    )
    return [(row[0], float(row[1])) for row in session.execute(query)]


def load_fund_prices(session: Session, code: str) -> Series:
    query = (
        select(FundPrice.date, FundPrice.price)
        .join(Fund, Fund.id == FundPrice.fund_id)
        .where(Fund.code == code)
        .order_by(FundPrice.date)
    )
    return [(row[0], float(row[1])) for row in session.execute(query)]


def fx_series(currency: str, start: dt.date) -> Series:
    """Yahoo'dan <PARA>TRY kuru (TCMB kuru değil, piyasa kuru)."""
    history = fetch_history(f"{currency}TRY=X", start)
    return [
        (date, float(close)) for date, close in zip(history["date"], history["close"], strict=True)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fon ile kopya portföyün getiri farkı")
    parser.add_argument("fund")
    parser.add_argument("--cash-rate", type=float, default=0.40, help="TL varlık getirisi")
    parser.add_argument("--fee", type=float, default=0.025, help="Yıllık yönetim ücreti")
    args = parser.parse_args()
    code = args.fund.upper()

    with Session(get_engine()) as session:
        holdings = latest_holdings(session, code)
        start = holdings[0].report_date
        fund_prices = load_fund_prices(session, code)
        end = fund_prices[-1][0]
        days = (end - start).days
        fund_return = period_return(fund_prices, start, end)
        if fund_return is None or days <= 0:
            raise SystemExit("Rapor sonrası fon fiyatı yok; TEFAS fiyatlarını güncelle")

        fx_cache: dict[str, float | None] = {"TRY": 0.0}

        def fx_return(currency: str | None) -> float | None:
            key = currency or "TRY"
            if key not in fx_cache:
                series = fx_series(key, start - dt.timedelta(days=10))
                fx_cache[key] = period_return(series, start, end)
            return fx_cache[key]

        positions: list[Position] = []
        for holding in holdings:
            symbol = to_yahoo(holding.asset, holding.asset_type)
            fx = fx_return(holding.currency)
            if symbol is not None:  # hisse
                local = period_return(load_closes(session, storage_ticker(symbol)), start, end)
                tl = None if local is None or fx is None else to_tl(local, fx)
            elif holding.asset_type == "fx_cash":
                tl = fx
            else:  # tahvil, bono, repo, teminat, para piyasası fonu
                tl = cash_return(args.cash_rate, days)
            positions.append(Position(holding.asset, holding.weight, tl))

    result = replica_return(positions)
    gap = fund_return - result.portfolio_return
    print(f"{code} getiri farkı: {start} → {end} ({days} gün)")
    print(f"  Fonun gerçek getirisi   %{fund_return * 100:7.2f}")
    print(f"  Kopya portföy getirisi  %{result.portfolio_return * 100:7.2f}")
    print(f"  Fark (fon − kopya)      %{gap * 100:7.2f}")
    fee = cash_return(args.fee, days)
    print(f"  Bu dönemin ücret payı   %{fee * 100:7.2f} (fiyata gömülü)")
    print(f"  Kapsanan ağırlık        %{result.covered_weight * 100:7.2f}")
    print("En çok katkı:")
    for asset, value in reversed(result.contributions[-5:]):
        print(f"  {asset:<16} %{value * 100:+.2f}")
    print("En çok zarar:")
    for asset, value in result.contributions[:5]:
        print(f"  {asset:<16} %{value * 100:+.2f}")
    print("Not: Geçmiş getiri analizi; yatırım tavsiyesi değildir.")


if __name__ == "__main__":
    main()
