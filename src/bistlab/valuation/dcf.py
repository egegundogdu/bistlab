"""İndirgenmiş nakit akışı (DCF) değerlemesi ve sermaye maliyeti hesapları."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd


def capm_cost_of_equity(risk_free: float, beta: float, equity_risk_premium: float) -> float:
    """CAPM: özkaynak maliyeti = risksiz faiz + beta × hisse senedi risk primi."""
    return risk_free + beta * equity_risk_premium


def wacc(
    equity_value: float,
    debt_value: float,
    cost_of_equity: float,
    cost_of_debt: float,
    tax_rate: float,
) -> float:
    """Ağırlıklı ortalama sermaye maliyeti; borç maliyeti vergi kalkanı kadar düşer."""
    total = equity_value + debt_value
    if total <= 0:
        raise ValueError("Özkaynak + borç pozitif olmalı.")
    equity_weight = equity_value / total
    debt_weight = debt_value / total
    return equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1 - tax_rate)


def fisher_real_rate(nominal_rate: float, inflation: float) -> float:
    """Fisher denklemi: reel oran = (1 + nominal) / (1 + enflasyon) - 1."""
    return (1 + nominal_rate) / (1 + inflation) - 1


def present_value(cash_flows: Sequence[float], rate: float) -> float:
    """Yıl sonu nakit akışlarının bugünkü değeri; ilk akış 1 yıl sonra gelir."""
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows, start=1))


def terminal_value(last_cash_flow: float, rate: float, growth: float) -> float:
    """Gordon büyüme modeli: son akış × (1 + g) / (r - g), son tahmin yılı itibarıyla."""
    if rate <= growth:
        raise ValueError("İskonto oranı uzun vadeli büyümeden büyük olmalı.")
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
        """Firma değerinin ne kadarının terminal değerden geldiği (0-1)."""
        return self.pv_terminal / self.enterprise_value


def dcf_value(
    cash_flows: Sequence[float],
    rate: float,
    terminal_growth: float,
    net_debt: float,
    shares: float,
) -> DcfResult:
    """Serbest nakit akışı tahminlerinden firma değerini ve hisse başı değeri hesaplar."""
    if not cash_flows:
        raise ValueError("En az bir yıllık nakit akışı tahmini gerekli.")
    if shares <= 0:
        raise ValueError("Pay sayısı pozitif olmalı.")
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
    """Hisse başı değer: satırlar iskonto oranı (WACC), sütunlar uzun vadeli büyüme."""
    data = {
        g: [
            dcf_value(cash_flows, r, g, net_debt, shares).per_share if r > g else float("nan")
            for r in rates
        ]
        for g in growths
    }
    return pd.DataFrame(data, index=list(rates))


def convert_rate(rate: float, inflation_from: float, inflation_to: float) -> float:
    """Bir para birimindeki iskonto oranını diğerine çevirir (enflasyon farkı, Fisher)."""
    return (1 + rate) * (1 + inflation_to) / (1 + inflation_from) - 1


def blume_adjust(raw_beta: float) -> float:
    """Blume düzeltmesi: tahmini betayı zaman içinde 1'e doğru çeker."""
    return 0.67 * raw_beta + 0.33
