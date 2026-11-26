"""Türev araçlar ve fon röntgeni API servisleri."""

from __future__ import annotations

import math
from typing import Literal, Protocol

import pandas as pd

from bistlab.api.schemas import (
    FundOverlapOut,
    FundRiskOut,
    FundXrayOut,
    GreeksOut,
    HedgeOut,
    ImpliedVolOut,
    OptionOut,
    OverlapRow,
    WeightOut,
)
from bistlab.data.db import FundHolding
from bistlab.derivatives.binomial import binomial_price
from bistlab.derivatives.black_scholes import bs_price, greeks, implied_volatility
from bistlab.derivatives.futures import (
    contracts_needed,
    implied_rate,
    min_variance_hedge,
    theoretical_price,
)
from bistlab.derivatives.monte_carlo import monte_carlo_price
from bistlab.funds.xray import (
    TYPE_LABELS,
    aligned_beta,
    concentration,
    country_of,
    group_weights,
    holding_key,
    overlap,
)
from bistlab.portfolio.risk import (
    annualized_return,
    annualized_volatility,
    conditional_var,
    historical_var,
    max_drawdown,
)
from bistlab.valuation.beta import weekly_returns

Option = Literal["call", "put"]


class ToolSource(Protocol):
    def closes(self, ticker: str) -> pd.Series[float]: ...

    def fund_holdings(self, code: str) -> list[FundHolding]: ...

    def fund_prices(self, code: str) -> pd.Series[float]: ...


def option_report(
    spot: float,
    strike: float,
    days: int,
    rate: float,
    vol: float,
    option: Option,
    dividend_yield: float,
) -> OptionOut:
    years = days / 365
    r = math.log1p(rate)
    q = dividend_yield

    def bs(kind: Option) -> float:
        return bs_price(spot, strike, years, r, vol, option=kind, dividend_yield=q)

    def tree(american: bool) -> float:
        return binomial_price(
            spot, strike, years, r, vol, option=option, dividend_yield=q, american=american
        )

    g = greeks(spot, strike, years, r, vol, option=option, dividend_yield=q)
    mc = monte_carlo_price(spot, strike, years, r, vol, option=option, dividend_yield=q)
    parity = (bs("call") - bs("put")) - (
        spot * math.exp(-q * years) - strike * math.exp(-r * years)
    )
    return OptionOut(
        option=option,
        spot=spot,
        strike=strike,
        years=years,
        rate=rate,
        continuous_rate=r,
        vol=vol,
        black_scholes=bs(option),
        greeks=GreeksOut(delta=g.delta, gamma=g.gamma, vega=g.vega, theta=g.theta, rho=g.rho),
        binomial_european=tree(american=False),
        binomial_american=tree(american=True),
        monte_carlo=mc.price,
        monte_carlo_std_error=mc.std_error,
        put_call_parity_gap=parity,
    )


def implied_vol(
    price: float,
    spot: float,
    strike: float,
    days: int,
    rate: float,
    option: Option,
    dividend_yield: float,
) -> ImpliedVolOut:
    vol = implied_volatility(
        price=price,
        spot=spot,
        strike=strike,
        years=days / 365,
        rate=math.log1p(rate),
        option=option,
        dividend_yield=dividend_yield,
    )
    return ImpliedVolOut(implied_vol=vol, price=price, option=option)


def futures_hedge(
    source: ToolSource,
    tickers: list[str],
    index: str,
    value: float,
    days: int,
    rate: float,
    dividend_yield: float,
    years: int,
    multiplier: float | None,
) -> HedgeOut:
    """`python -m bistlab.derivatives.futures` ile aynı hesap (eşit ağırlıklı portföy)."""
    closes = pd.concat(
        [source.closes(t).rename(t) for t in [*tickers, index]], axis=1, join="inner"
    )
    cutoff = closes.index.max() - pd.Timedelta(days=365 * years)
    returns = closes[closes.index >= cutoff].pct_change().dropna()
    if len(returns) < 20:
        raise ValueError("Hedge oranı için yeterli ortak fiyat yok")
    portfolio = returns[tickers].mean(axis=1)
    hedge = min_variance_hedge(portfolio, returns[index])
    spot = float(closes[index].iloc[-1])
    horizon = days / 365
    futures = theoretical_price(spot, horizon, rate, dividend_yield)
    notional = hedge.ratio * value
    return HedgeOut(
        tickers=tickers,
        index=index,
        value=value,
        spot=spot,
        days=days,
        futures_price=futures,
        basis_pct=futures / spot - 1,
        implied_rate=implied_rate(futures, spot, horizon, dividend_yield),
        hedge_ratio=hedge.ratio,
        notional=notional,
        contracts=contracts_needed(notional, futures, multiplier) if multiplier else None,
        unhedged_vol=hedge.unhedged_vol,
        hedged_vol=hedge.hedged_vol,
        risk_reduction=1 - hedge.hedged_vol / hedge.unhedged_vol if hedge.unhedged_vol else 0.0,
    )


def weights(pairs: list[tuple[str, float]]) -> list[WeightOut]:
    return [WeightOut(name=name, weight=weight) for name, weight in group_weights(pairs)]


def fund_xray(source: ToolSource, code: str, years: int, compare: str | None) -> FundXrayOut:
    """`python -m bistlab.funds.xray` ile aynı hesap. Fon yoksa KeyError."""
    holdings = source.fund_holdings(code)
    if not holdings:
        raise KeyError(code)
    conc = concentration([h.weight for h in holdings])

    risk = None
    prices = source.fund_prices(code)
    if len(prices) > 30:
        start = prices.index[-1] - pd.DateOffset(years=years)
        window = prices[prices.index >= start]
        daily = window.pct_change().dropna()
        try:
            beta: float | None = aligned_beta(
                weekly_returns(window), weekly_returns(source.closes("XU100"))
            )
        except (ValueError, KeyError):
            beta = None
        risk = FundRiskOut(
            years=years,
            annual_return=annualized_return(daily),
            annual_vol=annualized_volatility(daily),
            max_drawdown=max_drawdown(daily),
            var_95=historical_var(daily),
            cvar_95=conditional_var(daily),
            beta_xu100=beta if beta is not None and math.isfinite(beta) else None,
        )

    overlap_out = None
    if compare:
        other = source.fund_holdings(compare)
        first = {holding_key(h): h.weight for h in holdings}
        second = {holding_key(h): h.weight for h in other}
        names = {holding_key(h): h.asset for h in holdings}
        common = sorted(set(first) & set(second), key=lambda key: -first[key])
        overlap_out = FundOverlapOut(
            other=compare,
            overlap=overlap(first, second),
            common=[
                OverlapRow(asset=names[key], first=first[key], second=second[key]) for key in common
            ],
        )

    return FundXrayOut(
        code=code,
        report_date=holdings[0].report_date,
        holdings=len(holdings),
        asset_types=weights(
            [(TYPE_LABELS.get(h.asset_type, h.asset_type), h.weight) for h in holdings]
        ),
        currencies=weights([(h.currency or "TRY", h.weight) for h in holdings]),
        countries=weights([(country_of(h.asset_type, h.isin), h.weight) for h in holdings]),
        non_try_share=sum(h.weight for h in holdings if (h.currency or "TRY") != "TRY"),
        top10=conc.top10,
        hhi=conc.hhi,
        effective_n=conc.effective_n,
        risk=risk,
        overlap=overlap_out,
    )
