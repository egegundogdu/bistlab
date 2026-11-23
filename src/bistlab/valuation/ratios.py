"""Temel finansal oranlar."""

from __future__ import annotations

import numpy as np
import pandas as pd


def current_ratio(current_assets: float, current_liabilities: float) -> float:
    """Cari oran = dönen varlıklar / kısa vadeli yükümlülükler."""
    if current_liabilities <= 0:
        raise ValueError("Kısa vadeli yükümlülükler pozitif olmalı.")
    return current_assets / current_liabilities


def cagr(start_value: float, end_value: float, years: float) -> float:
    """Yıllık bileşik büyüme oranı: (bitiş / başlangıç) ^ (1 / yıl) - 1."""
    if start_value <= 0 or end_value <= 0:
        raise ValueError("Başlangıç ve bitiş değerleri pozitif olmalı.")
    if years <= 0:
        raise ValueError("Yıl sayısı pozitif olmalı.")
    return float((end_value / start_value) ** (1 / years) - 1)


def _column(df: pd.DataFrame, name: str) -> pd.Series[float]:
    """Kalem varsa sütununu, yoksa NaN dolu bir seri döner."""
    if name in df.columns:
        return df[name].astype(float)
    return pd.Series(np.nan, index=df.index, dtype=float)


def compute_ratios(items: pd.DataFrame) -> pd.DataFrame:
    """Yıllık kalem tablosundan (satır: dönem sonu, sütun: kalem) temel oranları hesaplar.

    Eksik kalem ya da sıfıra bölme olan oranlar NaN olarak döner; hata vermez.
    """
    df = items.sort_index()
    revenue = _column(df, "Total Revenue")
    ebitda = _column(df, "EBITDA")
    net_income = _column(df, "Net Income")

    ratios = pd.DataFrame(
        {
            "revenue_growth": revenue / revenue.shift(1) - 1,
            "gross_margin": _column(df, "Gross Profit") / revenue,
            "ebitda_margin": ebitda / revenue,
            "net_margin": net_income / revenue,
            "roe": net_income / _column(df, "Common Stock Equity"),
            "current_ratio": _column(df, "Current Assets") / _column(df, "Current Liabilities"),
            "net_debt_to_ebitda": (
                _column(df, "Total Debt") - _column(df, "Cash And Cash Equivalents")
            )
            / ebitda,
            "interest_coverage": _column(df, "EBIT") / _column(df, "Interest Expense"),
        },
        index=df.index,
    )
    return ratios.replace([np.inf, -np.inf], np.nan)
