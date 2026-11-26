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
