"""Market multiples (P/E, P/B, EV/EBITDA, FCF yield) and cross-company comparison."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass

import pandas as pd
from sqlalchemy.orm import Session

from bistlab.data.db import get_engine
from bistlab.valuation.beta import load_closes
from bistlab.valuation.report import load_items
from bistlab.valuation.run import latest, latest_macro

# EVDS series that convert the reporting currency to TRY
FX_SERIES = {"USD": "TP.DK.USD.A.YTL", "EUR": "TP.DK.EUR.A.YTL"}


@dataclass(frozen=True)
class Multiples:
    ticker: str
    currency: str
    market_cap_try_bn: float
    pe: float
    pb: float
    ev_ebitda: float
    fcf_yield: float


def _value(items: pd.DataFrame, name: str, default: float = float("nan")) -> float:
    """Latest value of a line item; the default when the item is missing."""
    try:
        return latest(items, name)
    except ValueError:
        return default


def _ratio(numerator: float, denominator: float) -> float:
    """NaN when the denominator is not positive (loss, negative equity): meaningless."""
    return numerator / denominator if denominator > 0 else float("nan")


def compute_multiples(
    ticker: str, currency: str, price_try: float, fx_to_try: float, items: pd.DataFrame
) -> Multiples:
    """Multiples in the reporting currency from the latest annual financials and price."""
    shares = latest(items, "Ordinary Shares Number")
    market_cap = price_try * shares / fx_to_try
    net_debt = _value(items, "Total Debt", 0.0) - _value(items, "Cash And Cash Equivalents", 0.0)
    enterprise_value = market_cap + net_debt
    return Multiples(
        ticker=ticker,
        currency=currency,
        market_cap_try_bn=price_try * shares / 1e9,
        pe=_ratio(market_cap, _value(items, "Net Income")),
        pb=_ratio(market_cap, _value(items, "Common Stock Equity")),
        ev_ebitda=_ratio(enterprise_value, _value(items, "EBITDA")),
        fcf_yield=_value(items, "Free Cash Flow") / market_cap,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare company multiples.")
    parser.add_argument("tickers", nargs="+", help="Tickers, e.g. THYAO PGSUS ASELS")
    args = parser.parse_args()

    results: list[Multiples] = []
    with Session(get_engine()) as session:
        for ticker in args.tickers:
            items, currency = load_items(session, ticker)
            price_try = float(load_closes(session, ticker).iloc[-1])
            fx_to_try = latest_macro(session, FX_SERIES[currency]) if currency != "TRY" else 1.0
            results.append(compute_multiples(ticker.upper(), currency, price_try, fx_to_try, items))

    table = pd.DataFrame([asdict(m) for m in results]).set_index("ticker")
    table.columns = ["Currency", "Market cap (bn TRY)", "P/E", "P/B", "EV/EBITDA", "FCF yield"]
    numeric = table.drop(columns=["Currency"])
    print(table.round(2).to_string())
    print(f"\nMedian: {numeric.median().round(2).to_dict()}")
    print("\nLatest annual financials; NaN = loss or negative denominator (meaningless).")


if __name__ == "__main__":
    main()
