"""Cox-Ross-Rubinstein binomial tree: European and American option pricing."""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from bistlab.derivatives.black_scholes import OptionType

Vector = npt.NDArray[np.float64]


def _payoff(prices: Vector, strike: float, option: OptionType) -> Vector:
    if option == "call":
        return np.asarray(np.maximum(prices - strike, 0.0), dtype=np.float64)
    return np.asarray(np.maximum(strike - prices, 0.0), dtype=np.float64)


def binomial_price(
    spot: float,
    strike: float,
    years: float,
    rate: float,
    vol: float,
    option: OptionType = "call",
    dividend_yield: float = 0.0,
    steps: int = 500,
    american: bool = False,
) -> float:
    """CRR tree: u = e^(σ√Δt), d = 1/u, risk-neutral p = (e^((r-q)Δt) - d) / (u - d).

    For American options each node takes the larger of exercise and continuation value.
    """
    if steps < 1:
        raise ValueError("Number of steps must be at least 1.")
    if spot <= 0 or strike <= 0 or years <= 0 or vol <= 0:
        raise ValueError("Spot, strike, maturity and volatility must be positive.")
    dt = years / steps
    up = math.exp(vol * math.sqrt(dt))
    down = 1 / up
    p = (math.exp((rate - dividend_yield) * dt) - down) / (up - down)
    if not 0 < p < 1:
        raise ValueError("Risk-neutral probability outside (0, 1); increase the number of steps.")
    discount = math.exp(-rate * dt)

    j = np.arange(steps + 1, dtype=np.float64)
    values = _payoff(spot * up**j * down ** (steps - j), strike, option)
    for i in range(steps - 1, -1, -1):
        values = np.asarray(discount * (p * values[1:] + (1 - p) * values[:-1]), dtype=np.float64)
        if american:
            k = np.arange(i + 1, dtype=np.float64)
            exercise = _payoff(spot * up**k * down ** (i - k), strike, option)
            values = np.asarray(np.maximum(values, exercise), dtype=np.float64)
    return float(values[0])
