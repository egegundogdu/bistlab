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
