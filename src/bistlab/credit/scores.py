"""Muhasebe tabanlı kredi skorları: Altman Z''-skoru (gelişmekte olan piyasalar) ve sentetik not.

Kaynaklar:
- Altman (2005), gelişmekte olan piyasa şirketleri için Z''-skoru (EM Score, sabit 3,25).
- Damodaran, faiz karşılama oranından sentetik not ve temerrüt spreadi (büyük, finans dışı
  şirketler tablosu, Ocak 2026). Spreadler USD bazlıdır.
"""

from __future__ import annotations

import argparse
import math

import pandas as pd
from sqlalchemy.orm import Session

from bistlab.data.db import get_engine
from bistlab.valuation.report import load_items

ALTMAN_SAFE = 5.85
ALTMAN_DISTRESS = 4.35

# (alt sınır, not, spread): faiz karşılama oranı alt sınırın üstündeyse o not
RATING_TABLE: list[tuple[float, str, float]] = [
    (8.5, "AAA", 0.0040),
    (6.5, "AA", 0.0055),
    (5.5, "A+", 0.0070),
    (4.25, "A", 0.0078),
    (3.0, "A-", 0.0089),
    (2.5, "BBB", 0.0111),
    (2.25, "BB+", 0.0138),
    (2.0, "BB", 0.0184),
    (1.75, "B+", 0.0275),
    (1.5, "B", 0.0321),
    (1.25, "B-", 0.0509),
    (0.8, "CCC", 0.0885),
    (0.65, "CC", 0.1261),
    (0.2, "C", 0.1600),
    (-math.inf, "D", 0.1900),
]


def altman_z_em(
    working_capital: float,
    retained_earnings: float,
    ebit: float,
    total_assets: float,
    book_equity: float,
    total_liabilities: float,
) -> float:
    """Z'' = 3,25 + 6,56·X1 + 3,26·X2 + 6,72·X3 + 1,05·X4."""
    x1 = working_capital / total_assets
    x2 = retained_earnings / total_assets
    x3 = ebit / total_assets
    x4 = book_equity / total_liabilities
    return 3.25 + 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4


def altman_zone(z: float) -> str:
    if z > ALTMAN_SAFE:
        return "güvenli"
    if z < ALTMAN_DISTRESS:
        return "sıkıntı"
    return "gri"


def interest_coverage(ebit: float, interest_expense: float) -> float:
    """FVÖK / faiz gideri. Faiz gideri yoksa sonsuz."""
    interest = abs(interest_expense)
    if interest == 0:
        return math.inf
    return ebit / interest


def synthetic_rating(coverage: float) -> tuple[str, float]:
    for lower, rating, spread in RATING_TABLE:
        if coverage >= lower:
            return rating, spread
    raise ValueError(f"Geçersiz faiz karşılama oranı: {coverage}")


def item(df: pd.DataFrame, name: str) -> pd.Series[float]:
    if name not in df.columns:
        return pd.Series(math.nan, index=df.index, dtype=float)
    return df[name].astype(float)


def credit_table(items: pd.DataFrame) -> pd.DataFrame:
    """Her dönem için Z'', bölge, faiz karşılama, not ve spread."""
    working_capital = item(items, "Working Capital").fillna(
        item(items, "Current Assets") - item(items, "Current Liabilities")
    )
    columns = {
        "wc": working_capital,
        "re": item(items, "Retained Earnings"),
        "ebit": item(items, "EBIT"),
        "ta": item(items, "Total Assets"),
        "eq": item(items, "Stockholders Equity"),
        "tl": item(items, "Total Liabilities Net Minority Interest"),
        "interest": item(items, "Interest Expense").fillna(0.0),
    }
    data = pd.DataFrame(columns).dropna(subset=["wc", "re", "ebit", "ta", "eq", "tl"])
    rows = []
    for period, row in data.iterrows():
        # row["eq"]: row.eq bir pandas metodu olduğu için köşeli parantez şart
        z = altman_z_em(row["wc"], row["re"], row["ebit"], row["ta"], row["eq"], row["tl"])
        coverage = interest_coverage(row["ebit"], row["interest"])
        rating, spread = synthetic_rating(coverage)
        rows.append(
            {
                "period": period,
                "z": z,
                "zone": altman_zone(z),
                "coverage": coverage,
                "rating": rating,
                "spread": spread,
            }
        )
    return pd.DataFrame(rows).set_index("period") if rows else pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(description="Altman Z'' ve sentetik kredi notu")
    parser.add_argument("tickers", nargs="+")
    args = parser.parse_args()

    with Session(get_engine()) as session:
        for ticker in args.tickers:
            try:
                items, currency = load_items(session, ticker)
            except ValueError as error:
                print(f"\n{ticker.upper()}: {error}")
                continue
            table = credit_table(items)
            print(f"\n{ticker.upper()} ({currency})")
            if table.empty:
                print("  Yeterli kalem yok")
                continue
            print("  Dönem        Z''   Bölge     FVÖK/Faiz  Not   Spread")
            for period, row in table.iterrows():
                cov = row["coverage"]
                coverage = "∞" if math.isinf(cov) else f"{cov:.2f}"
                print(
                    f"  {str(period)[:10]}  {row['z']:5.2f}  {row['zone']:<8}  {coverage:>9}  "
                    f"{row['rating']:<4}  %{row['spread'] * 100:.2f}"
                )
    print("\nNot: Z'' bölgeleri: >5,85 güvenli, 4,35–5,85 gri, <4,35 sıkıntı.")
    print("Spreadler Damodaran (Ocak 2026) USD tablosundan; ülke spreadi dahil değil.")
    print("Kredi notu değil, eğitim amaçlı göstergedir; yatırım tavsiyesi değildir.")


if __name__ == "__main__":
    main()
