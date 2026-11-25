"""Fon röntgeni: dağılımlar, yoğunlaşma, risk, beta ve fon çakışması."""

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
    "equity_tr": "BIST hisse",
    "equity_foreign": "Yabancı hisse",
    "corporate_bond": "Özel sektör tahvili",
    "commercial_paper": "Finansman bonosu",
    "government_bond": "Devlet tahvili",
    "treasury_bill": "Hazine bonosu",
    "reverse_repo": "Ters repo",
    "derivative_margin": "VİOP teminatı",
    "fund_tr": "Yerli fon",
    "fund_foreign": "Yabancı fon",
    "fx_cash": "Döviz nakit",
    "deposit": "Mevduat",
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
    """Hissede ISIN'in ilk iki harfi (şirketin kayıtlı olduğu ülke), TL varlıklarda TR."""
    if asset_type == "equity_foreign" and isin:
        return isin[:2]
    if asset_type == "fx_cash":
        return "Döviz nakit"
    return "TR"


def concentration(weights: list[float]) -> Concentration:
    """HHI = ağırlık karelerinin toplamı; 1/HHI 'etkin varlık sayısı'."""
    total = sum(weights)
    shares = sorted((w / total for w in weights), reverse=True)
    hhi = sum(s * s for s in shares)
    return Concentration(top10=sum(shares[:10]), hhi=hhi, effective_n=1 / hhi)


def holding_key(holding: FundHolding) -> str:
    """BIST hissesinde kod (bazı raporlarda ISIN ayrı satıra kayıyor), diğerlerinde ISIN."""
    if holding.asset_type == "equity_tr":
        return holding.asset
    return holding.isin or holding.asset


def overlap(first: dict[str, float], second: dict[str, float]) -> float:
    """Ortak varlıklarda küçük ağırlıkların toplamı: 0 = ortak yok, 1 = aynı portföy."""
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
        print(f"  {label:<22} %{weight * 100:6.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fon röntgeni")
    parser.add_argument("fund")
    parser.add_argument("--compare", help="Çakışma için ikinci fon kodu")
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
                message = f"{args.compare} için rapor yok; önce kap_report ile yükle"
                raise SystemExit(message) from None

    print(f"{code} röntgeni (rapor {holdings[0].report_date})")
    print_table(
        "Varlık türü:",
        group_weights([(TYPE_LABELS.get(h.asset_type, h.asset_type), h.weight) for h in holdings]),
    )
    print_table("Para birimi:", group_weights([(h.currency or "TRY", h.weight) for h in holdings]))
    foreign = sum(h.weight for h in holdings if (h.currency or "TRY") != "TRY")
    print(f"  TL dışı toplam         %{foreign * 100:6.2f}")
    print_table(
        "Ülke:", group_weights([(country_of(h.asset_type, h.isin), h.weight) for h in holdings])
    )

    conc = concentration([h.weight for h in holdings])
    print("Yoğunlaşma:")
    print(f"  İlk 10 kalem           %{conc.top10 * 100:6.2f}")
    print(f"  HHI                    {conc.hhi:7.4f}")
    print(f"  Etkin kalem sayısı     {conc.effective_n:7.1f}  (toplam {len(holdings)})")

    start = prices.index[-1] - pd.DateOffset(years=args.years)
    window = prices[prices.index >= start]
    daily = window.pct_change().dropna()
    print(f"Risk (son {args.years} yıl, günlük TEFAS fiyatı):")
    print(f"  Yıllık getiri          %{annualized_return(daily) * 100:6.2f}")
    print(f"  Yıllık oynaklık        %{annualized_volatility(daily) * 100:6.2f}")
    print(f"  Maks. düşüş            %{max_drawdown(daily) * 100:6.2f}")
    print(f"  Günlük VaR %95         %{historical_var(daily) * 100:6.2f}")
    print(f"  Günlük CVaR %95        %{conditional_var(daily) * 100:6.2f}")

    fund_weekly = weekly_returns(window)
    print("Haftalık beta:")
    print(f"  BIST 100'e göre        {aligned_beta(fund_weekly, weekly_returns(xu100)):7.2f}")

    if other is not None:
        first = {holding_key(h): h.weight for h in holdings}
        second = {holding_key(h): h.weight for h in other}
        common = sorted(set(first) & set(second), key=lambda key: -first[key])
        names = {holding_key(h): h.asset for h in holdings}
        print(f"Çakışma ({code} ↔ {args.compare.upper()}): %{overlap(first, second) * 100:.2f}")
        for key in common:
            left, right = first[key] * 100, second[key] * 100
            print(f"  {names[key]:<16} %{left:5.2f} ↔ %{right:5.2f}")

    print("Not: Geçmiş veriye dayalı analiz; yatırım tavsiyesi değildir.")


if __name__ == "__main__":
    main()
