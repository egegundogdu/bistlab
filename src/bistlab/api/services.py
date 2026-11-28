"""API servisleri: veri kaynağından okur, mevcut analiz fonksiyonlarını çağırır.

Veri kaynağı bir arayüzdür (`DataSource`); üretimde veritabanı, testlerde sahte veri.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Protocol

import numpy as np

from bistlab.api.schemas import (
    BetaOut,
    FcfListOut,
    FcfOut,
    HistoricalOut,
    HistoricalRow,
    PerformanceOut,
    PricePoint,
    PricesOut,
    QualityOut,
    ReturnsOut,
    ScenarioOut,
    SecuritiesOut,
    SecurityOut,
    SeriesQualityOut,
    StressOut,
)
from bistlab.quality.prices import STATUS_ORDER, Bar, assess_all
from bistlab.real.view import (
    CPI_CODE,
    FX_CODES,
    MARKET,
    Points,
    annualize,
    cpi_for,
    fcf_yield,
    performance,
    value_asof,
)
from bistlab.stress.macro import (
    SCENARIOS,
    fit_all,
    max_weekly_move,
    scenario_impact,
    to_series,
    window_return,
    worst_window,
)

EARLIEST = dt.date(2000, 1, 1)


class DataSource(Protocol):
    def ping(self) -> bool: ...

    def bars(self) -> dict[str, list[Bar]]: ...

    def macro(self, code: str) -> Points: ...

    def prices(self, ticker: str, since: dt.date) -> Points: ...

    def fcf_inputs(self, ticker: str) -> tuple[dt.date, str, float, float] | None: ...


class CatalogSource(Protocol):
    def securities(self) -> list[tuple[str, dt.date, float]]: ...


class DataUnavailable(Exception):
    """Hesap için gerekli seri veritabanında yok."""


def finite(value: float) -> float | None:
    return value if math.isfinite(value) else None


def quality_report(source: DataSource, issues_only: bool = False) -> QualityOut:
    try:
        results = assess_all(source.bars())
    except SystemExit as error:
        raise DataUnavailable(str(error)) from None
    series = [
        SeriesQualityOut(
            ticker=q.ticker,
            market=q.market,
            first=q.first,
            last=q.last,
            bars=q.bars,
            coverage=q.coverage,
            missing=len(q.missing),
            stale=q.stale,
            jumps=len(q.jumps),
            suspicious=len(q.suspicious),
            flat_run=q.flat_run,
            provisional=q.provisional,
            status=q.status,
        )
        for q in results
        if not (issues_only and q.status == "Good")
    ]
    return QualityOut(
        summary={status: sum(q.status == status for q in results) for status in STATUS_ORDER},
        provisional=sum(q.provisional for q in results),
        series=series,
    )


def _cpi_and_usd(source: DataSource) -> tuple[dict[dt.date, float], Points]:
    cpi = dict(source.macro(CPI_CODE))
    usd = source.macro(FX_CODES["USD"])
    if not cpi or not usd:
        raise DataUnavailable("No CPI or USD/TRY series")
    return cpi, usd


def real_returns(source: DataSource, tickers: list[str], since: dt.date) -> ReturnsOut:
    cpi, usd = _cpi_and_usd(source)
    results: list[PerformanceOut] = []
    skipped: list[str] = []
    for ticker in [MARKET, *tickers]:
        prices = source.prices(ticker, since)
        if len(prices) < 2:
            skipped.append(ticker)
            continue
        p = performance(ticker, prices, cpi, usd)
        results.append(
            PerformanceOut(
                ticker=p.ticker,
                start=p.start,
                end=p.end,
                years=p.years,
                nominal=p.nominal,
                real=p.real,
                usd=p.usd,
                nominal_annual=finite(annualize(p.nominal, p.years)),
                real_annual=finite(annualize(p.real, p.years)),
                usd_annual=finite(annualize(p.usd, p.years)),
                cpi_estimated=p.cpi_estimated,
            )
        )
    cpi_change: float | None = None
    usd_change: float | None = None
    if results:
        start, end = results[0].start, results[0].end
        cpi_change = cpi_for(cpi, end)[0] / cpi_for(cpi, start)[0] - 1
        usd_start, usd_end = value_asof(usd, start), value_asof(usd, end)
        if usd_start and usd_end:
            usd_change = usd_end / usd_start - 1
    return ReturnsOut(
        cpi_change=cpi_change, usd_change=usd_change, results=results, skipped=skipped
    )


def real_fcf(source: DataSource, tickers: list[str]) -> FcfListOut:
    cpi, _ = _cpi_and_usd(source)
    results: list[FcfOut] = []
    skipped: list[str] = []
    for ticker in tickers:
        inputs = source.fcf_inputs(ticker)
        prices = source.prices(ticker, EARLIEST)
        if inputs is None or not prices:
            skipped.append(ticker)
            continue
        period_end, currency, fcf, shares = inputs
        fx = 1.0
        if currency != "TRY":
            fx_rate = value_asof(source.macro(FX_CODES.get(currency, "")), prices[-1][0])
            if currency not in FX_CODES or fx_rate is None:
                skipped.append(ticker)
                continue
            fx = fx_rate
        y = fcf_yield(ticker, currency, period_end, fcf, shares, prices[-1][1], fx, cpi)
        results.append(
            FcfOut(
                ticker=y.ticker,
                currency=y.currency,
                period_end=y.period_end,
                fcf=y.fcf,
                market_cap=y.market_cap,
                factor=y.factor,
                nominal_yield=y.nominal_yield,
                restated_yield=y.restated_yield,
            )
        )
    return FcfListOut(latest_cpi_month=max(cpi), results=results, skipped=skipped)


def macro_stress(
    source: DataSource, tickers: list[str], years: float, window: int, today: dt.date
) -> StressOut:
    since = today - dt.timedelta(days=round(365.25 * years))
    usd = source.macro(FX_CODES["USD"])
    market = source.prices(MARKET, EARLIEST)
    if not usd or len(market) <= window:
        raise DataUnavailable("USD/TRY ya da XU100 verisi yok")
    prices = {t: source.prices(t, EARLIEST) for t in tickers}
    recent_usd = [p for p in usd if p[0] >= since]
    betas = fit_all(
        {t: [p for p in pts if p[0] >= since] for t, pts in prices.items()},
        [p for p in market if p[0] >= since],
        recent_usd,
    )
    scenarios: list[ScenarioOut] = []
    for name, market_shock, fx_shock in SCENARIOS:
        impacts = {t: scenario_impact(b, market_shock, fx_shock) for t, b in betas.items()}
        portfolio = float(np.mean(list(impacts.values()))) if impacts else None
        scenarios.append(
            ScenarioOut(
                name=name,
                market_shock=market_shock,
                fx_shock=fx_shock,
                impacts=impacts,
                portfolio=portfolio,
            )
        )
    start_ts, end_ts, market_move = worst_window(to_series(market), window)
    start, end = start_ts.date(), end_ts.date()
    rows: list[HistoricalRow] = []
    for ticker, b in betas.items():
        actual = window_return(prices[ticker], start, end)
        if actual is None:
            continue
        model = scenario_impact(b, market_move, window_return(usd, start, end) or 0.0)
        rows.append(
            HistoricalRow(ticker=ticker, actual=actual, model=model, difference=actual - model)
        )
    max_fx = max_weekly_move(recent_usd)
    return StressOut(
        betas=[
            BetaOut(
                ticker=t,
                market=b.market,
                fx=b.fx,
                t_fx=b.t_fx,
                fx_used=b.fx_used,
                r2=b.r2,
                weeks=b.n,
            )
            for t, b in betas.items()
        ],
        scenarios=scenarios,
        max_weekly_fx_move=max_fx,
        fx_shock_out_of_sample=max(abs(f) for _, _, f in SCENARIOS) > max_fx,
        historical=HistoricalOut(
            start=start,
            end=end,
            market_move=market_move,
            fx_move=window_return(usd, start, end) or 0.0,
            in_sample=start >= since,
            rows=rows,
            mean_abs_difference=(
                float(np.mean([abs(r.difference) for r in rows])) if rows else None
            ),
        ),
    )


def securities(source: CatalogSource) -> SecuritiesOut:
    return SecuritiesOut(
        results=[
            SecurityOut(ticker=t, last_date=d, last_close=c)
            for t, d, c in sorted(source.securities())
        ]
    )


def price_history(source: DataSource, ticker: str, since: dt.date) -> PricesOut:
    points = source.prices(ticker, since)
    if not points:
        raise KeyError(ticker)
    return PricesOut(ticker=ticker, points=[PricePoint(date=d, close=c) for d, c in points])
