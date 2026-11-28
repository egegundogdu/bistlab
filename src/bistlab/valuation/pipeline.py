"""End-to-end DCF as a pure function (same steps as the `run.main` CLI).

Used by the API and the UI: the caller supplies the data; no network or database here.
WACC and long-term growth can optionally be overridden (the sliders in the UI).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from bistlab.valuation.assumptions import Assumptions
from bistlab.valuation.beta import beta, weekly_returns
from bistlab.valuation.dcf import blume_adjust, dcf_value, sensitivity_table
from bistlab.valuation.run import (
    adjust_for_leases,
    average_last,
    cost_of_capital,
    implied_growth,
    latest,
    project_cash_flows,
    terminal_growth,
)

BETA_WINDOW_DAYS = 730
RATE_STEPS = (-0.02, -0.01, 0.0, 0.01, 0.02)
GROWTH_STEPS = (-0.01, 0.0, 0.01)


@dataclass(frozen=True)
class Valuation:
    ticker: str
    currency: str
    raw_beta: float
    beta: float
    beta_note: str
    cost_of_equity: float
    model_wacc: float
    model_terminal_growth: float
    wacc: float
    terminal_growth: float
    base_fcf: float
    lease_adjusted: bool
    growth: tuple[float, ...]
    enterprise_value: float
    net_debt: float
    equity_value: float
    terminal_share: float
    per_share_try: float
    price_try: float
    implied_growth: float | None
    sensitivity_rates: list[float]
    sensitivity_growths: list[float]
    sensitivity: list[list[float]]

    @property
    def upside(self) -> float:
        return self.per_share_try / self.price_try - 1


def valuate(
    a: Assumptions,
    items: pd.DataFrame,
    currency: str,
    closes: pd.Series[float],
    market: pd.Series[float],
    usd_try: float,
    wacc_override: float | None = None,
    growth_override: float | None = None,
) -> Valuation:
    """Same calculation as `python -m bistlab.valuation.run`. ValueError on invalid input."""
    if currency != a.currency:
        raise ValueError(f"Assumption file says {a.currency}, database says {currency}.")

    cutoff = closes.index.max() - pd.Timedelta(days=BETA_WINDOW_DAYS)
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

    ke, model_rate = cost_of_capital(a, market_cap, total_debt, beta_value)
    model_g = terminal_growth(a)
    rate = model_rate if wacc_override is None else wacc_override
    g = model_g if growth_override is None else growth_override
    if rate <= g:
        raise ValueError("WACC must be greater than long-term growth.")

    flows = project_cash_flows(base_fcf, a.growth)
    result = dcf_value(flows, rate, g, net_debt, shares)
    implied = implied_growth(base_fcf, len(a.growth), rate, g, net_debt, shares, price_try / to_try)

    rates = [rate + d for d in RATE_STEPS]
    growths = [g + d for d in GROWTH_STEPS]
    table = sensitivity_table(flows, net_debt, shares, rates, growths) * to_try
    return Valuation(
        ticker=a.ticker,
        currency=a.currency,
        raw_beta=raw_beta,
        beta=beta_value,
        beta_note=beta_note,
        cost_of_equity=ke,
        model_wacc=model_rate,
        model_terminal_growth=model_g,
        wacc=rate,
        terminal_growth=g,
        base_fcf=base_fcf,
        lease_adjusted=a.lease_adjusted,
        growth=tuple(a.growth),
        enterprise_value=result.enterprise_value,
        net_debt=net_debt,
        equity_value=result.equity_value,
        terminal_share=result.terminal_share,
        per_share_try=result.per_share * to_try,
        price_try=price_try,
        implied_growth=implied,
        sensitivity_rates=rates,
        sensitivity_growths=growths,
        sensitivity=[[float(v) for v in row] for row in table.to_numpy()],
    )
