"""Accounting-based credit scores: Altman Z''-score (emerging markets) and synthetic rating.

Sources:
- Altman (2005), Z''-score for emerging-market companies (EM Score, constant 3.25).
- Damodaran, synthetic rating and default spread from interest coverage (large non-financial
  companies table, January 2026). Spreads are in USD terms.
"""

from __future__ import annotations

import argparse
import math

import pandas as pd
from sqlalchemy.orm import Session

from bistlab.common import column
from bistlab.data.db import get_engine
from bistlab.valuation.report import load_items

ALTMAN_SAFE = 5.85
ALTMAN_DISTRESS = 4.35

# (lower bound, rating, spread): the rating applies when interest coverage is above the bound
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
    """Z'' = 3.25 + 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4."""
    x1 = working_capital / total_assets
    x2 = retained_earnings / total_assets
    x3 = ebit / total_assets
    x4 = book_equity / total_liabilities
    return 3.25 + 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4


def altman_zone(z: float) -> str:
    if z > ALTMAN_SAFE:
        return "safe"
    if z < ALTMAN_DISTRESS:
        return "distress"
    return "grey"


def operating_profit(items: pd.DataFrame) -> pd.Series[float]:
    """Reported operating profit; falls back to Yahoo's EBIT.

    Yahoo derives EBIT from pre-tax profit plus interest. Under IAS 29 that includes the
    monetary loss and FX losses (ASELS 2022: EBIT TRY 1.1 bn, operating profit TRY 11.5 bn).
    """
    return column(items, "Operating Income").fillna(column(items, "EBIT"))


def interest_coverage(ebit: float, interest_expense: float) -> float:
    """EBIT / interest expense. Infinite when there is no interest expense."""
    interest = abs(interest_expense)
    if interest == 0:
        return math.inf
    return ebit / interest


def synthetic_rating(coverage: float) -> tuple[str, float]:
    for lower, rating, spread in RATING_TABLE:
        if coverage >= lower:
            return rating, spread
    raise ValueError(f"Invalid interest coverage ratio: {coverage}")


def credit_table(items: pd.DataFrame) -> pd.DataFrame:
    """Z'', zone, interest coverage, rating and spread for every period."""
    working_capital = column(items, "Working Capital").fillna(
        column(items, "Current Assets") - column(items, "Current Liabilities")
    )
    columns = {
        "wc": working_capital,
        "re": column(items, "Retained Earnings"),
        "ebit": operating_profit(items),
        "ta": column(items, "Total Assets"),
        "eq": column(items, "Stockholders Equity"),
        "tl": column(items, "Total Liabilities Net Minority Interest"),
        "interest": column(items, "Interest Expense").fillna(0.0),
    }
    data = pd.DataFrame(columns).dropna(subset=["wc", "re", "ebit", "ta", "eq", "tl"])
    rows = []
    for period, row in data.iterrows():
        # row["eq"], not row.eq: .eq is a pandas method
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
    parser = argparse.ArgumentParser(description="Altman Z'' and synthetic credit rating")
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
                print("  Not enough line items")
                continue
            print(f"  {'Period':<10}  {'Z':>5}  {'Zone':<8}  {'EBIT/int.':>9}  {'Rtg':<4}  Spread")
            for period, row in table.iterrows():
                cov = row["coverage"]
                coverage = "∞" if math.isinf(cov) else f"{cov:.2f}"
                print(
                    f"  {str(period)[:10]}  {row['z']:5.2f}  {row['zone']:<8}  {coverage:>9}  "
                    f"{row['rating']:<4}  {row['spread'] * 100:.2f}%"
                )
    print("\nNote: Z'' zones: >5.85 safe, 4.35–5.85 grey, <4.35 distress.")
    print("Spreads from Damodaran's USD table (January 2026); no country spread included.")
    print("An educational indicator, not a credit rating; not investment advice.")


if __name__ == "__main__":
    main()
