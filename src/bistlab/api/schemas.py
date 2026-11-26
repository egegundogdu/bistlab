"""API yanıt modelleri."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

DISCLAIMER = "Eğitim amaçlıdır; yatırım tavsiyesi değildir."


class Health(BaseModel):
    status: str
    database: bool


class SeriesQualityOut(BaseModel):
    ticker: str
    market: str
    first: dt.date
    last: dt.date
    bars: int
    coverage: float
    missing: int
    stale: int
    jumps: int
    suspicious: int
    flat_run: int
    provisional: bool
    status: str


class QualityOut(BaseModel):
    summary: dict[str, int]
    provisional: int
    series: list[SeriesQualityOut]


class PerformanceOut(BaseModel):
    ticker: str
    start: dt.date
    end: dt.date
    years: float
    nominal: float
    real: float
    usd: float
    nominal_annual: float | None
    real_annual: float | None
    usd_annual: float | None
    cpi_estimated: bool


class ReturnsOut(BaseModel):
    cpi_change: float | None
    usd_change: float | None
    results: list[PerformanceOut]
    skipped: list[str]
    disclaimer: str = DISCLAIMER


class FcfOut(BaseModel):
    ticker: str
    currency: str
    period_end: dt.date
    fcf: float
    market_cap: float
    factor: float
    nominal_yield: float
    restated_yield: float


class FcfListOut(BaseModel):
    latest_cpi_month: dt.date
    results: list[FcfOut]
    skipped: list[str]
    disclaimer: str = DISCLAIMER


class BetaOut(BaseModel):
    ticker: str
    market: float
    fx: float
    t_fx: float
    fx_used: float
    r2: float
    weeks: int


class ScenarioOut(BaseModel):
    name: str
    market_shock: float
    fx_shock: float
    impacts: dict[str, float]
    portfolio: float | None


class HistoricalRow(BaseModel):
    ticker: str
    actual: float
    model: float
    difference: float


class HistoricalOut(BaseModel):
    start: dt.date
    end: dt.date
    market_move: float
    fx_move: float
    in_sample: bool
    rows: list[HistoricalRow]
    mean_abs_difference: float | None


class StressOut(BaseModel):
    betas: list[BetaOut]
    scenarios: list[ScenarioOut]
    max_weekly_fx_move: float
    fx_shock_out_of_sample: bool
    historical: HistoricalOut
    disclaimer: str = DISCLAIMER


class CreditRow(BaseModel):
    period: dt.date
    z: float | None
    zone: str
    coverage: float | None  # None: faiz gideri yok (sonsuz karşılama)
    rating: str
    spread: float


class CreditCompany(BaseModel):
    ticker: str
    currency: str
    rows: list[CreditRow]


class CreditOut(BaseModel):
    results: list[CreditCompany]
    skipped: list[str]
    note: str = (
        "Altman Z'' (EM) ve Damodaran sentetik notu (Ocak 2026, USD spread); "
        "faaliyet kârı Yahoo EBIT'i yerine esas faaliyet kârı."
    )
    disclaimer: str = DISCLAIMER


class MertonCompany(BaseModel):
    ticker: str
    period: str
    market_cap: float
    default_point: float
    equity_vol: float
    asset_value: float
    asset_vol: float
    distance_to_default: float
    default_probability: float


class MertonOut(BaseModel):
    rate: float
    results: list[MertonCompany]
    skipped: list[str]
    note: str = (
        "Piyasa değeri = veritabanındaki son kapanış × hisse sayısı; yabancı para borç TCMB "
        "kuruyla TL'ye çevrilir. CLI canlı Yahoo verisi kullandığı için küçük farklar olabilir. "
        "PD risk-nötr ve 1 yıllıktır; kredi notu değildir."
    )
    disclaimer: str = DISCLAIMER


class MultiplesRow(BaseModel):
    ticker: str
    currency: str
    market_cap_try_bn: float | None
    pe: float | None
    pb: float | None
    ev_ebitda: float | None
    fcf_yield: float | None


class MultiplesOut(BaseModel):
    results: list[MultiplesRow]
    median: dict[str, float | None]
    skipped: list[str]
    note: str = "Son yıllık finansallar; boş değer = zarar ya da negatif payda (anlamsız çarpan)."
    disclaimer: str = DISCLAIMER


class IndicatorOut(BaseModel):
    section: str
    name: str
    score: float | None
    raw: str


class GovernanceCompany(BaseModel):
    ticker: str
    sections: dict[str, float]
    total: float
    answered: int
    indicators: list[IndicatorOut] | None = None


class GovernanceOut(BaseModel):
    results: list[GovernanceCompany]
    skipped: list[str]
    note: str = (
        "0-10 ölçeği; SPK ağırlıkları: pay sahipleri %25, kamuyu aydınlatma %25, menfaat "
        "sahipleri %15, yönetim kurulu %35. Şirket beyanına (KAP KYBF) dayanır, "
        "derecelendirme notu değildir."
    )
    disclaimer: str = DISCLAIMER


class GreeksOut(BaseModel):
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


class OptionOut(BaseModel):
    option: str
    spot: float
    strike: float
    years: float
    rate: float
    continuous_rate: float
    vol: float
    black_scholes: float
    greeks: GreeksOut
    binomial_european: float
    binomial_american: float
    monte_carlo: float
    monte_carlo_std_error: float
    put_call_parity_gap: float
    note: str = (
        "rate yıllık efektif faizdir; modellere ln(1+r) sürekli faiz olarak girer. "
        "Vega/rho 1 puan, theta 1 takvim günü içindir. Parite farkı ≈ 0 olmalı."
    )
    disclaimer: str = DISCLAIMER


class ImpliedVolOut(BaseModel):
    implied_vol: float
    price: float
    option: str


class HedgeOut(BaseModel):
    tickers: list[str]
    index: str
    value: float
    spot: float
    days: int
    futures_price: float
    basis_pct: float
    implied_rate: float
    hedge_ratio: float
    notional: float
    contracts: float | None
    unhedged_vol: float
    hedged_vol: float
    risk_reduction: float
    note: str = (
        "Vadeli fiyat teorik (taşıma maliyeti); hedge oranı günlük getirilerle minimum varyans "
        "betası. Hedge sonrası kalan risk şirkete özgü risktir."
    )
    disclaimer: str = DISCLAIMER


class WeightOut(BaseModel):
    name: str
    weight: float


class FundRiskOut(BaseModel):
    years: int
    annual_return: float
    annual_vol: float
    max_drawdown: float
    var_95: float
    cvar_95: float
    beta_xu100: float | None


class OverlapRow(BaseModel):
    asset: str
    first: float
    second: float


class FundOverlapOut(BaseModel):
    other: str
    overlap: float
    common: list[OverlapRow]


class FundXrayOut(BaseModel):
    code: str
    report_date: dt.date
    holdings: int
    asset_types: list[WeightOut]
    currencies: list[WeightOut]
    countries: list[WeightOut]
    non_try_share: float
    top10: float
    hhi: float
    effective_n: float
    risk: FundRiskOut | None
    overlap: FundOverlapOut | None
    disclaimer: str = DISCLAIMER


class SecurityOut(BaseModel):
    ticker: str
    last_date: dt.date
    last_close: float


class SecuritiesOut(BaseModel):
    results: list[SecurityOut]


class PricePoint(BaseModel):
    date: dt.date
    close: float


class PricesOut(BaseModel):
    ticker: str
    points: list[PricePoint]
