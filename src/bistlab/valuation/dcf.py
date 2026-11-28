"""Discounted cash flow (DCF) valuation and cost of capital."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd


def capm_cost_of_equity(risk_free: float, beta: float, equity_risk_premium: float) -> float:
    """CAPM: cost of equity = risk-free rate + beta × equity risk premium."""
    return risk_free + beta * equity_risk_premium


def wacc(
    equity_value: float,
    debt_value: float,
    cost_of_equity: float,
    cost_of_debt: float,
    tax_rate: float,
) -> float:
    """Weighted average cost of capital; the cost of debt is reduced by the tax shield."""
    total = equity_value + debt_value
    if total <= 0:
        raise ValueError("Equity + debt must be positive.")
    equity_weight = equity_value / total
    debt_weight = debt_value / total
    return equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1 - tax_rate)


def fisher_real_rate(nominal_rate: float, inflation: float) -> float:
    """Fisher equation: real rate = (1 + nominal) / (1 + inflation) - 1."""
    return (1 + nominal_rate) / (1 + inflation) - 1


def present_value(cash_flows: Sequence[float], rate: float) -> float:
    """Present value of year-end cash flows; the first flow arrives in one year."""
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows, start=1))


def terminal_value(last_cash_flow: float, rate: float, growth: float) -> float:
    """Gordon growth model: last flow × (1 + g) / (r - g), as of the final forecast year."""
    if rate <= growth:
        raise ValueError("Discount rate must be greater than long-term growth.")
    return last_cash_flow * (1 + growth) / (rate - growth)


@dataclass(frozen=True)
class DcfResult:
    pv_cash_flows: float
    pv_terminal: float
    enterprise_value: float
    equity_value: float
    per_share: float

    @property
    def terminal_share(self) -> float:
        """Share of enterprise value that comes from the terminal value (0-1)."""
        return self.pv_terminal / self.enterprise_value


def dcf_value(
    cash_flows: Sequence[float],
    rate: float,
    terminal_growth: float,
    net_debt: float,
    shares: float,
) -> DcfResult:
    """Enterprise value and value per share from free cash flow forecasts."""
    if not cash_flows:
        raise ValueError("At least one year of cash flow forecasts is required.")
    if shares <= 0:
        raise ValueError("Share count must be positive.")
    pv_cf = present_value(cash_flows, rate)
    pv_tv = terminal_value(cash_flows[-1], rate, terminal_growth) / (1 + rate) ** len(cash_flows)
    enterprise = pv_cf + pv_tv
    equity = enterprise - net_debt
    return DcfResult(pv_cf, pv_tv, enterprise, equity, equity / shares)


def sensitivity_table(
    cash_flows: Sequence[float],
    net_debt: float,
    shares: float,
    rates: Sequence[float],
    growths: Sequence[float],
) -> pd.DataFrame:
    """Value per share: rows are discount rates (WACC), columns long-term growth."""
    data = {
        g: [
            dcf_value(cash_flows, r, g, net_debt, shares).per_share if r > g else float("nan")
            for r in rates
        ]
        for g in growths
    }
    return pd.DataFrame(data, index=list(rates))


def convert_rate(rate: float, inflation_from: float, inflation_to: float) -> float:
    """Converts a discount rate between currencies (inflation differential, Fisher)."""
    return (1 + rate) * (1 + inflation_to) / (1 + inflation_from) - 1


def blume_adjust(raw_beta: float) -> float:
    """Blume adjustment: pulls the estimated beta toward 1 over time."""
    return 0.67 * raw_beta + 0.33
