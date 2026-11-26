"""API testleri için sahte veri kaynağı (veritabanı gerektirmez)."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from bistlab.quality.prices import Bar
from bistlab.real.view import CPI_CODE, FX_CODES, Points

TODAY = dt.date(2026, 11, 24)


def business_days(start: dt.date, end: dt.date) -> list[dt.date]:
    days, day = [], start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += dt.timedelta(days=1)
    return days


class FakeSource:
    def __init__(self, healthy: bool = True, with_macro: bool = True) -> None:
        rng = np.random.default_rng(7)
        self.days = business_days(dt.date(2023, 1, 2), TODAY)
        n = len(self.days)
        market = 5000 * np.cumprod(1 + rng.normal(0.001, 0.015, n))
        usd = 18.7 * np.cumprod(1 + rng.normal(0.001, 0.003, n))
        self.series: dict[str, Points] = {
            "XU100": list(zip(self.days, market, strict=True)),
            "THYAO": list(
                zip(self.days, market * 0.03 * (1 + rng.normal(0, 0.01, n)), strict=True)
            ),
            "ASELS": list(
                zip(self.days, market * 0.01 * (1 + rng.normal(0, 0.01, n)), strict=True)
            ),
        }
        self.usd: Points = list(zip(self.days, usd, strict=True))
        months = [dt.date(y, m, 1) for y in range(2022, 2027) for m in range(1, 13)]
        months = [m for m in months if m <= dt.date(2026, 10, 1)]
        self.cpi: Points = [(m, 40.0 * 1.03**i) for i, m in enumerate(months)]
        self.healthy = healthy
        self.with_macro = with_macro

    def ping(self) -> bool:
        return self.healthy

    def bars(self) -> dict[str, list[Bar]]:
        return {t: [Bar(d, float(c), None) for d, c in pts] for t, pts in self.series.items()}

    def macro(self, code: str) -> Points:
        if not self.with_macro:
            return []
        if code == CPI_CODE:
            return self.cpi
        return self.usd if code == FX_CODES["USD"] else []

    def prices(self, ticker: str, since: dt.date) -> Points:
        return [(d, float(c)) for d, c in self.series.get(ticker, []) if d >= since]

    def fcf_inputs(self, ticker: str) -> tuple[dt.date, str, float, float] | None:
        if ticker == "THYAO":
            return dt.date(2025, 12, 31), "USD", 2.0e9, 1.0e9
        if ticker == "ASELS":
            return dt.date(2025, 12, 31), "TRY", 10.0e9, 4.0e9
        return None

    def items(self, ticker: str) -> tuple[pd.DataFrame, str]:
        periods = pd.DatetimeIndex(["2024-12-31", "2025-12-31"])
        base = {
            "Working Capital": [20e9, 25e9],
            "Retained Earnings": [60e9, 70e9],
            "Operating Income": [15e9, 18e9],
            "Total Assets": [200e9, 220e9],
            "Stockholders Equity": [100e9, 110e9],
            "Common Stock Equity": [100e9, 110e9],
            "Total Liabilities Net Minority Interest": [100e9, 110e9],
            "Interest Expense": [3e9, 4e9],
            "Total Debt": [40e9, 45e9],
            "Current Debt": [10e9, 12e9],
            "Cash And Cash Equivalents": [8e9, 9e9],
            "Net Income": [12e9, 14e9],
            "EBITDA": [20e9, 24e9],
            "Free Cash Flow": [5e9, 6e9],
            "Ordinary Shares Number": [4e9, 4e9],
        }
        if ticker == "ASELS":
            return pd.DataFrame(base, index=periods), "TRY"
        if ticker == "THYAO":
            usd = {k: [v / 40 for v in vals] for k, vals in base.items()}
            usd["Ordinary Shares Number"] = [1.4e9, 1.4e9]
            return pd.DataFrame(usd, index=periods), "USD"
        raise ValueError(f"{ticker}: finansal tablo yok")

    def closes(self, ticker: str) -> pd.Series[float]:
        points = self.series.get(ticker)
        if not points:
            raise ValueError(f"{ticker}: fiyat yok")
        index = pd.DatetimeIndex([pd.Timestamp(d) for d, _ in points])
        return pd.Series([float(c) for _, c in points], index=index)

    def latest_fx(self, currency: str) -> float:
        if currency != "USD":
            raise KeyError(currency)
        return float(self.usd[-1][1])

    def governance_files(self) -> dict[str, str]:
        return {}
