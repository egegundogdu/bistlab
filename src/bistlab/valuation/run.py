"""End-to-end DCF valuation from an assumptions file and database data."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from bistlab.data.db import MacroObservation, get_engine
from bistlab.valuation import assumptions as assumptions_file
from bistlab.valuation.assumptions import Assumptions
from bistlab.valuation.beta import beta, load_closes, weekly_returns
from bistlab.valuation.dcf import (
    blume_adjust,
    capm_cost_of_equity,
    convert_rate,
    dcf_value,
    sensitivity_table,
    wacc,
)
from bistlab.valuation.report import load_items

USD_TRY = "TP.DK.USD.A.YTL"
MARKET_INDEX = "XU100"


def latest(items: pd.DataFrame, name: str) -> float:
    """Latest non-empty value of a line item."""
    return average_last(items, name, 1)


def average_last(items: pd.DataFrame, name: str, years: int) -> float:
    """Mean of the non-empty values of a line item over the last `years` years."""
    if name not in items.columns:
        raise ValueError(f"Line item '{name}' not found.")
    series = items[name].dropna().sort_index().tail(years)
    if series.empty:
        raise ValueError(f"Line item '{name}' is empty.")
    return float(series.mean())


def project_cash_flows(base: float, growth: Sequence[float]) -> list[float]:
    """Grows the base cash flow forward with annual growth rates."""
    flows: list[float] = []
    value = base
    for g in growth:
        value *= 1 + g
        flows.append(value)
    return flows


def adjust_for_leases(
    items: pd.DataFrame, base_fcf: float, total_debt: float, years: int
) -> tuple[float, float]:
    """Treats leases as an operating expense: (adjusted FCF, adjusted debt).

    The annual lease payment, approximated by the current lease liability, is deducted from FCF;
    lease liabilities are removed from debt, so cash flow and debt stay consistent.
    """
    lease_payment = average_last(items, "Current Capital Lease Obligation", years)
    lease_liabilities = latest(items, "Capital Lease Obligations")
    return base_fcf - lease_payment, total_debt - lease_liabilities


def cost_of_capital(
    a: Assumptions, equity_value: float, debt_value: float, beta_value: float
) -> tuple[float, float]:
    """(cost of equity, WACC) in the reporting currency.

    The cost of equity comes from a USD-based CAPM; for companies reporting in TRY it is
    converted to TRY with the inflation differential.
    """
    ke_usd = capm_cost_of_equity(a.usd_risk_free, beta_value, a.equity_risk_premium)
    if a.currency == "USD":
        ke = ke_usd
    else:
        ke = convert_rate(ke_usd, a.us_inflation, a.local_inflation)
    return ke, wacc(equity_value, debt_value, ke, a.pre_tax_cost_of_debt, a.tax_rate)


def terminal_growth(a: Assumptions) -> float:
    """Nominal terminal growth = (1 + real growth) × (1 + long-term inflation) - 1."""
    inflation = a.us_inflation if a.currency == "USD" else a.local_inflation
    return (1 + a.terminal_real_growth) * (1 + inflation) - 1


def implied_growth(
    base_fcf: float,
    years: int,
    rate: float,
    g_terminal: float,
    net_debt: float,
    shares: float,
    target_per_share: float,
) -> float | None:
    """Reverse DCF: constant annual FCF growth that gives the target value per share (bisection).

    Returns None when the base FCF is not positive or there is no solution in [-50%, +300%].
    """
    if base_fcf <= 0:
        return None

    def value(growth: float) -> float:
        flows = project_cash_flows(base_fcf, [growth] * years)
        return dcf_value(flows, rate, g_terminal, net_debt, shares).per_share

    low, high = -0.5, 3.0
    if not value(low) <= target_per_share <= value(high):
        return None
    for _ in range(200):
        mid = (low + high) / 2
        if value(mid) < target_per_share:
            low = mid
        else:
            high = mid
        if high - low < 1e-7:
            break
    return (low + high) / 2


def latest_macro(session: Session, code: str) -> float:
    """Latest value of a macro series."""
    query = (
        select(MacroObservation.value)
        .where(MacroObservation.code == code)
        .order_by(MacroObservation.date.desc())
        .limit(1)
    )
    value = session.scalar(query)
    if value is None:
        raise ValueError(f"No data for {code}. Run bistlab.data.evds first.")
    return float(value)


def _bn(value: float) -> str:
    return f"{value / 1e9:,.1f} bn"


def main() -> None:
    parser = argparse.ArgumentParser(description="DCF valuation from an assumptions file.")
    parser.add_argument("ticker", help="Ticker; assumptions/<TICKER>.toml must exist")
    args = parser.parse_args()

    a = assumptions_file.load(args.ticker)
    with Session(get_engine()) as session:
        items, currency = load_items(session, a.ticker)
        closes = load_closes(session, a.ticker)
        market = load_closes(session, MARKET_INDEX)
        usd_try = latest_macro(session, USD_TRY)
    if currency != a.currency:
        raise ValueError(f"Assumption file says {a.currency}, database says {currency}.")

    cutoff = closes.index.max() - pd.Timedelta(days=730)
    raw_beta = beta(
        weekly_returns(closes[closes.index >= cutoff]),
        weekly_returns(market[market.index >= cutoff]),
    )
    if a.beta_override is not None:
        beta_value, beta_note = a.beta_override, "manual"
    elif a.use_blume:
        beta_value, beta_note = blume_adjust(raw_beta), "Blume-adjusted"
    else:
        beta_value, beta_note = raw_beta, "raw"

    to_try = 1.0 if a.currency == "TRY" else usd_try
    price_try = float(closes.iloc[-1])
    shares = latest(items, "Ordinary Shares Number")
    market_cap = price_try * shares / to_try

    total_debt = latest(items, "Total Debt")
    base_fcf = average_last(items, "Free Cash Flow", a.base_fcf_years)
    if a.lease_adjusted:
        base_fcf, total_debt = adjust_for_leases(items, base_fcf, total_debt, a.base_fcf_years)
    net_debt = total_debt - latest(items, "Cash And Cash Equivalents")

    ke, rate = cost_of_capital(a, market_cap, total_debt, beta_value)
    g = terminal_growth(a)
    flows = project_cash_flows(base_fcf, a.growth)
    result = dcf_value(flows, rate, g, net_debt, shares)
    value_try = result.per_share * to_try
    cur = a.currency

    print(f"{a.ticker} | reporting currency: {cur}\n")
    print(f"Beta: raw {raw_beta:.2f} → used {beta_value:.2f} ({beta_note})")
    print(f"Cost of equity: {ke:.1%} | WACC: {rate:.1%} | Terminal growth: {g:.1%}")
    lease_note = "lease-adjusted" if a.lease_adjusted else "not lease-adjusted"
    print(f"Base FCF ({a.base_fcf_years}-year avg., {lease_note}): {_bn(base_fcf)} {cur}")
    print(f"Enterprise value: {_bn(result.enterprise_value)} {cur}", end="")
    print(f" | Net debt: {_bn(net_debt)} {cur}")
    print(f"Terminal value share: {result.terminal_share:.0%}")
    print(f"\nValue per share: {value_try:,.2f} TRY | Last price: {price_try:,.2f} TRY", end="")
    print(f" | Upside: {value_try / price_try - 1:+.0%}")

    implied = implied_growth(base_fcf, len(a.growth), rate, g, net_debt, shares, price_try / to_try)
    if implied is None:
        print("Reverse DCF: no solution (negative base FCF or out of range).")
    else:
        print(
            f"Reverse DCF: the current price implies {implied * 100:.1f}% annual FCF growth "
            f"for {len(a.growth)} years (in {cur})."
        )

    rates = [rate + d for d in (-0.02, -0.01, 0.0, 0.01, 0.02)]
    growths = [g + d for d in (-0.01, 0.0, 0.01)]
    table = sensitivity_table(flows, net_debt, shares, rates, growths) * to_try
    table.index = [f"WACC {r:.1%}" for r in rates]
    table.columns = [f"g {x:.1%}" for x in growths]
    print("\nSensitivity (TRY per share):")
    print(table.round(2).to_string())
    print("\nFor education; not investment advice.")


if __name__ == "__main__":
    main()
