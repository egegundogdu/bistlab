"""bistlab HTTP API (salt okunur).

Çalıştırma: `uv run uvicorn bistlab.api.main:app --reload` → http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import text

from bistlab.api import services
from bistlab.api.schemas import FcfListOut, Health, QualityOut, ReturnsOut, StressOut
from bistlab.api.services import DataSource, DataUnavailable
from bistlab.data.db import get_engine
from bistlab.quality.prices import Bar, load_bars
from bistlab.real.view import DEFAULT_TICKERS, Points, latest_fcf_inputs, load_macro, load_prices

TICKER = re.compile(r"^[A-Z0-9.]{1,16}$")


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


def get_source() -> DataSource:
    return DatabaseSource()


Source = Annotated[DataSource, Depends(get_source)]
Tickers = Annotated[list[str] | None, Query(description="Kodlar; boşsa 8 ana hisse")]

app = FastAPI(
    title="bistlab",
    version="0.1.0",
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
