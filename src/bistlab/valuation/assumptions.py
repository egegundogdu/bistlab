"""Reads company-level valuation assumptions from a TOML file."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ASSUMPTIONS_DIR = Path("assumptions")


@dataclass(frozen=True)
class Assumptions:
    ticker: str
    currency: str
    usd_risk_free: float
    equity_risk_premium: float
    us_inflation: float
    local_inflation: float
    beta_override: float | None
    use_blume: bool
    pre_tax_cost_of_debt: float
    tax_rate: float
    base_fcf_years: int
    growth: tuple[float, ...]
    terminal_real_growth: float
    lease_adjusted: bool


def parse(data: dict[str, Any]) -> Assumptions:
    """Converts TOML content into an Assumptions object."""
    company, market, capital, forecast = (
        data["company"],
        data["market"],
        data["capital"],
        data["forecast"],
    )
    beta_section = data.get("beta", {})
    return Assumptions(
        ticker=str(company["ticker"]).upper(),
        currency=str(company["currency"]).upper(),
        usd_risk_free=float(market["usd_risk_free"]),
        equity_risk_premium=float(market["equity_risk_premium"]),
        us_inflation=float(market["us_inflation"]),
        local_inflation=float(market.get("local_inflation", market["us_inflation"])),
        beta_override=float(beta_section["value"]) if "value" in beta_section else None,
        use_blume=bool(beta_section.get("use_blume", True)),
        pre_tax_cost_of_debt=float(capital["pre_tax_cost_of_debt"]),
        tax_rate=float(capital["tax_rate"]),
        base_fcf_years=int(forecast.get("base_fcf_years", 1)),
        growth=tuple(float(g) for g in forecast["growth"]),
        terminal_real_growth=float(forecast["terminal_real_growth"]),
        lease_adjusted=bool(forecast.get("lease_adjusted", False)),
    )


def load(ticker: str, directory: Path = ASSUMPTIONS_DIR) -> Assumptions:
    """Reads assumptions/<TICKER>.toml."""
    path = directory / f"{ticker.strip().upper()}.toml"
    with path.open("rb") as handle:
        return parse(tomllib.load(handle))
