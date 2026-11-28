"""Fund X-ray: breakdowns, concentration, risk, beta and overlap between funds."""

from __future__ import annotations

import argparse
import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

import pandas as pd
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from bistlab.data.db import FundHolding, get_engine
from bistlab.funds.holding_prices import latest_holdings
from bistlab.funds.replica import load_fund_prices
from bistlab.portfolio.risk import (
    annualized_return,
    annualized_volatility,
    conditional_var,
    historical_var,
    max_drawdown,
)
from bistlab.valuation.beta import beta, load_closes, weekly_returns

TYPE_LABELS = {
    "equity_tr": "BIST equity",
    "equity_foreign": "Foreign equity",
    "corporate_bond": "Corporate bond",
    "commercial_paper": "Commercial paper",
    "government_bond": "Government bond",
    "treasury_bill": "Treasury bill",
    "reverse_repo": "Reverse repo",
    "derivative_margin": "Derivatives margin",
    "fund_tr": "Domestic fund",
    "fund_foreign": "Foreign fund",
    "fx_cash": "FX cash",
    "deposit": "Deposit",
}


@dataclass(frozen=True)
class Concentration:
    top10: float
    hhi: float
    effective_n: float


def group_weights(items: list[tuple[str, float]]) -> list[tuple[str, float]]:
    totals: dict[str, float] = defaultdict(float)
    for label, weight in items:
        totals[label] += weight
    return sorted(totals.items(), key=lambda item: -item[1])


def country_of(asset_type: str, isin: str | None) -> str:
    """For stocks the first two ISIN letters (country of incorporation); TR for TRY assets."""
    if asset_type == "equity_foreign" and isin:
        return isin[:2]
    if asset_type == "fx_cash":
        return "FX cash"
    return "TR"


def concentration(weights: list[float]) -> Concentration:
    """HHI = sum of squared weights; 1/HHI is the 'effective number of holdings'."""
    total = sum(weights)
    shares = sorted((w / total for w in weights), reverse=True)
    hhi = sum(s * s for s in shares)
    return Concentration(top10=sum(shares[:10]), hhi=hhi, effective_n=1 / hhi)


def holding_key(holding: FundHolding) -> str:
    """Ticker for BIST stocks (some reports push the ISIN to another line), else the ISIN."""
    if holding.asset_type == "equity_tr":
        return holding.asset
    return holding.isin or holding.asset


def overlap(first: dict[str, float], second: dict[str, float]) -> float:
    """Sum of the smaller weights of shared holdings: 0 = nothing shared, 1 = same portfolio."""
    return sum(min(weight, second[key]) for key, weight in first.items() if key in second)


def to_series(rows: list[tuple[dt.date, float]]) -> pd.Series[float]:
    dates = pd.DatetimeIndex([date for date, _ in rows])
    return pd.Series([value for _, value in rows], index=dates, dtype=float)


def aligned_beta(asset: pd.Series[float], market: pd.Series[float]) -> float:
    frame = pd.concat([asset, market], axis=1, join="inner").dropna()
    return beta(frame.iloc[:, 0], frame.iloc[:, 1])


def print_table(title: str, rows: list[tuple[str, float]], limit: int = 8) -> None:
    print(title)
    for label, weight in rows[:limit]:
        print(f"  {label:<22} {weight * 100:6.2f}%")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fund X-ray")
    parser.add_argument("fund")
    parser.add_argument("--compare", help="Second fund code for overlap")
    parser.add_argument("--years", type=int, default=2)
    args = parser.parse_args()
    code = args.fund.upper()

    with Session(get_engine()) as session:
        holdings = latest_holdings(session, code)
        prices = to_series(load_fund_prices(session, code))
        xu100 = load_closes(session, "XU100")
        other = None
        if args.compare:
            try:
                other = latest_holdings(session, args.compare.upper())
            except NoResultFound:
                message = f"No report for {args.compare}; load it with kap_report first"
                raise SystemExit(message) from None

    print(f"{code} X-ray (report {holdings[0].report_date})")
    print_table(
        "Asset type:",
        group_weights([(TYPE_LABELS.get(h.asset_type, h.asset_type), h.weight) for h in holdings]),
    )
    print_table("Currency:", group_weights([(h.currency or "TRY", h.weight) for h in holdings]))
    foreign = sum(h.weight for h in holdings if (h.currency or "TRY") != "TRY")
    print(f"  Non-TRY total          {foreign * 100:6.2f}%")
    print_table(
        "Country:", group_weights([(country_of(h.asset_type, h.isin), h.weight) for h in holdings])
    )

    conc = concentration([h.weight for h in holdings])
    print("Concentration:")
    print(f"  Top 10 holdings        {conc.top10 * 100:6.2f}%")
    print(f"  HHI                    {conc.hhi:7.4f}")
    print(f"  Effective holdings     {conc.effective_n:7.1f}  (of {len(holdings)})")

    start = prices.index[-1] - pd.DateOffset(years=args.years)
    window = prices[prices.index >= start]
    daily = window.pct_change().dropna()
    print(f"Risk (last {args.years} years, daily TEFAS prices):")
    print(f"  Annual return          {annualized_return(daily) * 100:6.2f}%")
    print(f"  Annual volatility      {annualized_volatility(daily) * 100:6.2f}%")
    print(f"  Max drawdown           {max_drawdown(daily) * 100:6.2f}%")
    print(f"  Daily VaR 95%          {historical_var(daily) * 100:6.2f}%")
    print(f"  Daily CVaR 95%         {conditional_var(daily) * 100:6.2f}%")

    fund_weekly = weekly_returns(window)
    print("Weekly beta:")
    print(f"  vs BIST 100            {aligned_beta(fund_weekly, weekly_returns(xu100)):7.2f}")

    if other is not None:
        first = {holding_key(h): h.weight for h in holdings}
        second = {holding_key(h): h.weight for h in other}
        common = sorted(set(first) & set(second), key=lambda key: -first[key])
        names = {holding_key(h): h.asset for h in holdings}
        print(f"Overlap ({code} ↔ {args.compare.upper()}): {overlap(first, second) * 100:.2f}%")
        for key in common:
            left, right = first[key] * 100, second[key] * 100
            print(f"  {names[key]:<16} {left:5.2f}% ↔ {right:5.2f}%")

    print("Note: based on historical data; not investment advice.")


if __name__ == "__main__":
    main()
