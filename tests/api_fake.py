"""API testleri için sahte veri kaynağı (veritabanı gerektirmez)."""

from __future__ import annotations

import datetime as dt

import numpy as np

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
