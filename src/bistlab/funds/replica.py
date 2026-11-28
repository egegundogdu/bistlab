"""Return gap: the fund's actual return vs. a replica built from its reported holdings.

What would the fund have earned if the reported holdings had not changed all month?
The gap combines intra-month trading, transaction costs and the management fee.
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
    tl_return: float | None  # None: no price data


@dataclass(frozen=True)
class ReplicaResult:
    portfolio_return: float
    covered_weight: float
    contributions: list[tuple[str, float]]


def value_on(series: Series, day: dt.date) -> float | None:
    """Last value on or before the day."""
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
    """Return of the holdings with data, their weights rescaled to sum to 1."""
    known = [p for p in positions if p.tl_return is not None]
    covered = sum(p.weight for p in known)
    if covered <= 0:
        raise ValueError("No holdings with a computable return")
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
    """<CCY>TRY rate from Yahoo (market rate, not the central bank rate)."""
    history = fetch_history(f"{currency}TRY=X", start)
    return [
        (date, float(close)) for date, close in zip(history["date"], history["close"], strict=True)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Return gap between a fund and its replica portfolio"
    )
    parser.add_argument("fund")
    parser.add_argument("--cash-rate", type=float, default=0.40, help="Return on TRY assets")
    parser.add_argument("--fee", type=float, default=0.025, help="Annual management fee")
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
            raise SystemExit("No fund prices after the report; update TEFAS prices")

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
            if symbol is not None:  # stock
                local = period_return(load_closes(session, storage_ticker(symbol)), start, end)
                tl = None if local is None or fx is None else to_tl(local, fx)
            elif holding.asset_type == "fx_cash":
                tl = fx
            else:  # bonds, bills, repo, margin, money market funds
                tl = cash_return(args.cash_rate, days)
            positions.append(Position(holding.asset, holding.weight, tl))

    result = replica_return(positions)
    gap = fund_return - result.portfolio_return
    print(f"{code} return gap: {start} → {end} ({days} days)")
    print(f"  Fund actual return      {fund_return * 100:7.2f}%")
    print(f"  Replica return          {result.portfolio_return * 100:7.2f}%")
    print(f"  Gap (fund − replica)    {gap * 100:7.2f}%")
    fee = cash_return(args.fee, days)
    print(f"  Fee for the period      {fee * 100:7.2f}% (in the price)")
    print(f"  Covered weight          {result.covered_weight * 100:7.2f}%")
    print("Top contributors:")
    for asset, value in reversed(result.contributions[-5:]):
        print(f"  {asset:<16} {value * 100:+.2f}%")
    print("Top detractors:")
    for asset, value in result.contributions[:5]:
        print(f"  {asset:<16} {value * 100:+.2f}%")
    print("Note: historical analysis; not investment advice.")


if __name__ == "__main__":
    main()
