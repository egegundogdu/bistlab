"""Core financial ratios."""

from __future__ import annotations

import numpy as np
import pandas as pd

from bistlab.common import column


def current_ratio(current_assets: float, current_liabilities: float) -> float:
    """Current ratio = current assets / current liabilities."""
    if current_liabilities <= 0:
        raise ValueError("Current liabilities must be positive.")
    return current_assets / current_liabilities


def cagr(start_value: float, end_value: float, years: float) -> float:
    """Compound annual growth rate: (end / start) ^ (1 / years) - 1."""
    if start_value <= 0 or end_value <= 0:
        raise ValueError("Start and end values must be positive.")
    if years <= 0:
        raise ValueError("Number of years must be positive.")
    return float((end_value / start_value) ** (1 / years) - 1)


def compute_ratios(items: pd.DataFrame) -> pd.DataFrame:
    """Core ratios from the annual line-item table (rows: period end, columns: items).

    Ratios with a missing item or division by zero come back as NaN; no error is raised.
    """
    df = items.sort_index()
    revenue = column(df, "Total Revenue")
    ebitda = column(df, "EBITDA")
    net_income = column(df, "Net Income")

    ratios = pd.DataFrame(
        {
            "revenue_growth": revenue / revenue.shift(1) - 1,
            "gross_margin": column(df, "Gross Profit") / revenue,
            "ebitda_margin": ebitda / revenue,
            "net_margin": net_income / revenue,
            "roe": net_income / column(df, "Common Stock Equity"),
            "current_ratio": column(df, "Current Assets") / column(df, "Current Liabilities"),
            "net_debt_to_ebitda": (
                column(df, "Total Debt") - column(df, "Cash And Cash Equivalents")
            )
            / ebitda,
            "interest_coverage": column(df, "EBIT") / column(df, "Interest Expense"),
        },
        index=df.index,
    )
    return ratios.replace([np.inf, -np.inf], np.nan)
