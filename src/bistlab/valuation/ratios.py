"""Temel finansal oranlar."""

from __future__ import annotations


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
