"""bistlab HTTP API (salt okunur).

Çalıştırma: `uv run uvicorn bistlab.api.main:app --reload` → http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Annotated, Literal, Protocol

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from bistlab.api import core, services, tools
from bistlab.api.core import CoreSource
from bistlab.api.schemas import (
    CreditOut,
    FcfListOut,
    FundXrayOut,
    GovernanceOut,
    Health,
    HedgeOut,
    ImpliedVolOut,
    MertonOut,
    MultiplesOut,
    OptionOut,
    QualityOut,
    ReturnsOut,
    StressOut,
)
from bistlab.api.services import DataSource, DataUnavailable
from bistlab.api.tools import ToolSource
from bistlab.data.db import FundHolding, get_engine
from bistlab.funds.holding_prices import latest_holdings
from bistlab.funds.replica import load_fund_prices
from bistlab.funds.xray import to_series
from bistlab.quality.prices import Bar, load_bars
from bistlab.real.view import DEFAULT_TICKERS, Points, latest_fcf_inputs, load_macro, load_prices
from bistlab.valuation.beta import load_closes
from bistlab.valuation.multiples import FX_SERIES
from bistlab.valuation.report import load_items
from bistlab.valuation.run import latest_macro

TICKER = re.compile(r"^[A-Z0-9.]{1,16}$")
GOVERNANCE_DIR = Path("data/kap")


class FullSource(DataSource, CoreSource, ToolSource, Protocol):
    """API'nin ihtiyaç duyduğu tüm okuma işlemleri."""


class DatabaseSource:
    """Üretim veri kaynağı: PostgreSQL."""

    def ping(self) -> bool:
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def bars(self) -> dict[str, list[Bar]]:
        return load_bars()

    def macro(self, code: str) -> Points:
        with get_engine().connect() as conn:
            return load_macro(conn, code)

    def prices(self, ticker: str, since: dt.date) -> Points:
        with get_engine().connect() as conn:
            return load_prices(conn, ticker, since)

    def fcf_inputs(self, ticker: str) -> tuple[dt.date, str, float, float] | None:
        with get_engine().connect() as conn:
            return latest_fcf_inputs(conn, ticker)

    def items(self, ticker: str) -> tuple[pd.DataFrame, str]:
        with Session(get_engine()) as session:
            return load_items(session, ticker)

    def closes(self, ticker: str) -> pd.Series[float]:
        with Session(get_engine()) as session:
            return load_closes(session, ticker)

    def latest_fx(self, currency: str) -> float:
        if currency not in FX_SERIES:
            raise KeyError(currency)
        with Session(get_engine()) as session:
            return float(latest_macro(session, FX_SERIES[currency]))

    def fund_holdings(self, code: str) -> list[FundHolding]:
        with Session(get_engine()) as session:
            try:
                return latest_holdings(session, code)
            except NoResultFound:
                raise KeyError(code) from None

    def fund_prices(self, code: str) -> pd.Series[float]:
        with Session(get_engine()) as session:
            return to_series(load_fund_prices(session, code))

    def governance_files(self) -> dict[str, str]:
        return {
            path.stem.split("_")[0].upper(): path.read_text(encoding="utf-8")
            for path in sorted(GOVERNANCE_DIR.glob("*_kybf.xls"))
        }


def get_source() -> FullSource:
    return DatabaseSource()


Source = Annotated[FullSource, Depends(get_source)]
Tickers = Annotated[list[str] | None, Query(description="Kodlar; boşsa 8 ana hisse")]

app = FastAPI(
    title="bistlab",
    version="0.3.0",
    description="BIST analiz ve risk platformu — salt okunur API. "
    "Eğitim amaçlıdır; yatırım tavsiyesi değildir.",
)


def clean_tickers(tickers: list[str] | None) -> list[str]:
    codes = [t.strip().upper() for t in (tickers or DEFAULT_TICKERS)]
    bad = [t for t in codes if not TICKER.match(t)]
    if bad:
        raise HTTPException(status_code=422, detail=f"Geçersiz kod: {', '.join(bad)}")
    return codes


def unavailable(error: DataUnavailable) -> HTTPException:
    return HTTPException(status_code=503, detail=str(error))


@app.get("/health")
def health(source: Source) -> Health:
    return Health(status="ok", database=source.ping())


@app.get("/quality/prices")
def quality_prices(source: Source, issues_only: bool = False) -> QualityOut:
    try:
        return services.quality_report(source, issues_only)
    except DataUnavailable as error:
        raise unavailable(error) from None


@app.get("/real/returns")
def real_returns(
    source: Source, tickers: Tickers = None, since: dt.date = dt.date(2023, 1, 2)
) -> ReturnsOut:
    try:
        return services.real_returns(source, clean_tickers(tickers), since)
    except DataUnavailable as error:
        raise unavailable(error) from None


@app.get("/real/fcf")
def real_fcf(source: Source, tickers: Tickers = None) -> FcfListOut:
    try:
        return services.real_fcf(source, clean_tickers(tickers))
    except DataUnavailable as error:
        raise unavailable(error) from None


@app.get("/stress/macro")
def stress_macro(
    source: Source,
    tickers: Tickers = None,
    years: Annotated[float, Query(gt=0, le=10)] = 2.0,
    window: Annotated[int, Query(ge=1, le=60)] = 5,
) -> StressOut:
    try:
        return services.macro_stress(source, clean_tickers(tickers), years, window, dt.date.today())
    except DataUnavailable as error:
        raise unavailable(error) from None


@app.get("/credit/scores")
def credit_scores(source: Source, tickers: Tickers = None) -> CreditOut:
    return core.credit_scores(source, clean_tickers(tickers))


@app.get("/credit/merton")
def credit_merton(
    source: Source,
    tickers: Tickers = None,
    rate: Annotated[float, Query(ge=0, le=2, description="Yıllık basit TL risksiz faiz")] = 0.40,
) -> MertonOut:
    return core.merton(source, clean_tickers(tickers), rate)


@app.get("/valuation/multiples")
def valuation_multiples(source: Source, tickers: Tickers = None) -> MultiplesOut:
    return core.multiples(source, clean_tickers(tickers))


@app.get("/governance/scores")
def governance_scores(source: Source, detail: bool = False) -> GovernanceOut:
    return core.governance(source, detail)


OptionType = Annotated[Literal["call", "put"], Query(alias="type")]
Positive = Annotated[float, Query(gt=0)]
Days = Annotated[int, Query(ge=1, le=3650, description="Vadeye kalan takvim günü")]
Rate = Annotated[float, Query(ge=-0.5, le=3, description="Yıllık efektif faiz")]
Yield = Annotated[float, Query(ge=0, le=1)]


@app.get("/derivatives/option")
def derivatives_option(
    spot: Positive,
    strike: Positive,
    days: Days = 30,
    rate: Rate = 0.40,
    vol: Annotated[float, Query(gt=0, le=5)] = 0.35,
    option: OptionType = "call",
    dividend_yield: Yield = 0.0,
) -> OptionOut:
    try:
        return tools.option_report(spot, strike, days, rate, vol, option, dividend_yield)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@app.get("/derivatives/implied-vol")
def derivatives_implied_vol(
    price: Positive,
    spot: Positive,
    strike: Positive,
    days: Days = 30,
    rate: Rate = 0.40,
    option: OptionType = "call",
    dividend_yield: Yield = 0.0,
) -> ImpliedVolOut:
    try:
        return tools.implied_vol(price, spot, strike, days, rate, option, dividend_yield)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@app.get("/derivatives/futures-hedge")
def derivatives_futures_hedge(
    source: Source,
    tickers: Tickers = None,
    index: str = "XU030",
    value: Positive = 1_000_000,
    days: Days = 60,
    rate: Rate = 0.40,
    dividend_yield: Yield = 0.0,
    years: Annotated[int, Query(ge=1, le=5)] = 1,
    multiplier: Annotated[float | None, Query(gt=0, description="VİOP kontrat çarpanı")] = None,
) -> HedgeOut:
    codes = clean_tickers(tickers)
    index_code = clean_tickers([index])[0]
    try:
        return tools.futures_hedge(
            source, codes, index_code, value, days, rate, dividend_yield, years, multiplier
        )
    except (ValueError, KeyError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@app.get("/funds/{code}/xray")
def funds_xray(
    source: Source,
    code: str,
    years: Annotated[int, Query(ge=1, le=10)] = 2,
    compare: str | None = None,
) -> FundXrayOut:
    fund = clean_tickers([code])[0]
    other = clean_tickers([compare])[0] if compare else None
    try:
        return tools.fund_xray(source, fund, years, other)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Fon raporu yok: {error}") from None
