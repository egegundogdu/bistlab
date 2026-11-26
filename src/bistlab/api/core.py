"""Lisans modüllerinin API servisleri: kredi riski, Merton, çarpanlar, kurumsal yönetim."""

from __future__ import annotations

import datetime as dt
import math
from typing import Protocol

import numpy as np
import pandas as pd

from bistlab.api.schemas import (
    CreditCompany,
    CreditOut,
    CreditRow,
    DcfOut,
    GovernanceCompany,
    GovernanceOut,
    IndicatorOut,
    MertonCompany,
    MertonOut,
    MultiplesOut,
    MultiplesRow,
)
from bistlab.credit.merton import default_point, latest_debt, solve_merton
from bistlab.credit.scores import credit_table
from bistlab.governance.scorecard import read_form, score_form, section_scores, total_score
from bistlab.portfolio.risk import annualized_volatility
from bistlab.valuation.assumptions import Assumptions
from bistlab.valuation.multiples import compute_multiples
from bistlab.valuation.pipeline import valuate
from bistlab.valuation.run import latest

TRADING_DAYS = 253


class CoreSource(Protocol):
    def items(self, ticker: str) -> tuple[pd.DataFrame, str]: ...

    def closes(self, ticker: str) -> pd.Series[float]: ...

    def latest_fx(self, currency: str) -> float: ...

    def governance_files(self) -> dict[str, str]: ...

    def assumptions(self, ticker: str) -> Assumptions: ...


def finite(value: float) -> float | None:
    return float(value) if math.isfinite(value) else None


def period_date(period: object) -> dt.date:
    return dt.date.fromisoformat(str(period)[:10])


def credit_scores(source: CoreSource, tickers: list[str]) -> CreditOut:
    results: list[CreditCompany] = []
    skipped: list[str] = []
    for ticker in tickers:
        try:
            items, currency = source.items(ticker)
        except (ValueError, KeyError):
            skipped.append(ticker)
            continue
        table = credit_table(items)
        rows = [
            CreditRow(
                period=period_date(period),
                z=finite(float(row["z"])),
                zone=str(row["zone"]),
                coverage=finite(float(row["coverage"])),
                rating=str(row["rating"]),
                spread=float(row["spread"]),
            )
            for period, row in table.iterrows()
        ]
        if not rows:
            skipped.append(ticker)
            continue
        results.append(CreditCompany(ticker=ticker, currency=currency, rows=rows))
    return CreditOut(results=results, skipped=skipped)


def merton(source: CoreSource, tickers: list[str], rate: float) -> MertonOut:
    """`rate` yıllık basit TL faizi; modele sürekli bileşik (log1p) olarak girer."""
    continuous = math.log1p(rate)
    results: list[MertonCompany] = []
    skipped: list[str] = []
    for ticker in tickers:
        try:
            items, currency = source.items(ticker)
            period, short, long = latest_debt(items)
            closes = source.closes(ticker)
            shares = latest(items, "Ordinary Shares Number")
            market_cap = float(closes.iloc[-1]) * shares
            fx = 1.0 if currency == "TRY" else source.latest_fx(currency)
            debt = default_point(short, long) * fx
            returns = closes.iloc[-TRADING_DAYS:].pct_change().dropna()
            equity_vol = float(annualized_volatility(returns))
            result = solve_merton(market_cap, equity_vol, debt, continuous)
        except (ValueError, KeyError, IndexError):
            skipped.append(ticker)
            continue
        if not math.isfinite(market_cap) or market_cap <= 0:
            skipped.append(ticker)
            continue
        results.append(
            MertonCompany(
                ticker=ticker,
                period=period,
                market_cap=market_cap,
                default_point=debt,
                equity_vol=equity_vol,
                asset_value=result.asset_value,
                asset_vol=result.asset_vol,
                distance_to_default=result.distance_to_default,
                default_probability=result.default_probability,
            )
        )
    return MertonOut(rate=rate, results=results, skipped=skipped)


def multiples(source: CoreSource, tickers: list[str]) -> MultiplesOut:
    results: list[MultiplesRow] = []
    skipped: list[str] = []
    for ticker in tickers:
        try:
            items, currency = source.items(ticker)
            price = float(source.closes(ticker).iloc[-1])
            fx = 1.0 if currency == "TRY" else source.latest_fx(currency)
            m = compute_multiples(ticker, currency, price, fx, items)
        except (ValueError, KeyError, IndexError):
            skipped.append(ticker)
            continue
        results.append(
            MultiplesRow(
                ticker=m.ticker,
                currency=m.currency,
                market_cap_try_bn=finite(m.market_cap_try_bn),
                pe=finite(m.pe),
                pb=finite(m.pb),
                ev_ebitda=finite(m.ev_ebitda),
                fcf_yield=finite(m.fcf_yield),
            )
        )
    median: dict[str, float | None] = {}
    for field in ("pe", "pb", "ev_ebitda", "fcf_yield"):
        values = [v for r in results if (v := getattr(r, field)) is not None]
        median[field] = float(np.median(values)) if values else None
    return MultiplesOut(results=results, median=median, skipped=skipped)


def governance(source: CoreSource, detail: bool = False) -> GovernanceOut:
    results: list[GovernanceCompany] = []
    skipped: list[str] = []
    for ticker, html in sorted(source.governance_files().items()):
        try:
            indicators = score_form(read_form(html))
            scores = section_scores(indicators)
            total = total_score(scores)
        except (ValueError, KeyError, IndexError, ZeroDivisionError):
            skipped.append(ticker)
            continue
        results.append(
            GovernanceCompany(
                ticker=ticker,
                sections={name: value * 10 for name, value in scores.items()},
                total=total,
                answered=sum(i.score is not None for i in indicators),
                indicators=(
                    [
                        IndicatorOut(section=i.section, name=i.name, score=i.score, raw=i.raw[:120])
                        for i in indicators
                    ]
                    if detail
                    else None
                ),
            )
        )
    results.sort(key=lambda c: c.total, reverse=True)
    return GovernanceOut(results=results, skipped=skipped)


def dcf(
    source: CoreSource,
    ticker: str,
    wacc: float | None = None,
    terminal_growth: float | None = None,
) -> DcfOut:
    """Varsayım dosyası yoksa KeyError, hesap geçersizse ValueError."""
    try:
        a = source.assumptions(ticker)
    except (FileNotFoundError, OSError) as error:
        raise KeyError(ticker) from error
    items, currency = source.items(ticker)
    v = valuate(
        a,
        items,
        currency,
        source.closes(ticker),
        source.closes("XU100"),
        source.latest_fx("USD"),
        wacc,
        terminal_growth,
    )
    return DcfOut(
        ticker=v.ticker,
        currency=v.currency,
        raw_beta=v.raw_beta,
        beta=v.beta,
        beta_note=v.beta_note,
        cost_of_equity=v.cost_of_equity,
        model_wacc=v.model_wacc,
        model_terminal_growth=v.model_terminal_growth,
        wacc=v.wacc,
        terminal_growth=v.terminal_growth,
        base_fcf=v.base_fcf,
        lease_adjusted=v.lease_adjusted,
        growth=list(v.growth),
        enterprise_value=v.enterprise_value,
        net_debt=v.net_debt,
        equity_value=v.equity_value,
        terminal_share=v.terminal_share,
        per_share_try=v.per_share_try,
        price_try=v.price_try,
        upside=v.upside,
        implied_growth=v.implied_growth,
        sensitivity_rates=v.sensitivity_rates,
        sensitivity_growths=v.sensitivity_growths,
        sensitivity=v.sensitivity,
    )
