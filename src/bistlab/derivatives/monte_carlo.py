"""Monte Carlo pricing of European options (antithetic variance reduction)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from bistlab.derivatives.black_scholes import OptionType


@dataclass(frozen=True)
class McResult:
    price: float
    std_error: float

    def confidence_interval(self, z: float = 1.96) -> tuple[float, float]:
        """Confidence interval, 95% by default."""
        return self.price - z * self.std_error, self.price + z * self.std_error


def monte_carlo_price(
    spot: float,
    strike: float,
    years: float,
    rate: float,
    vol: float,
    option: OptionType = "call",
    dividend_yield: float = 0.0,
    paths: int = 100_000,
    seed: int = 42,
    antithetic: bool = True,
) -> McResult:
    """Simulates terminal prices (geometric Brownian motion); averages the discounted payoff.

    Antithetic variates: each z is paired with -z, lowering the error for the same paths.
    """
    if paths < 2:
        raise ValueError("At least 2 paths are required.")
    rng = np.random.default_rng(seed)
    half = paths // 2
    z = rng.standard_normal(half if antithetic else paths)
    if antithetic:
        z = np.concatenate([z, -z])

    drift = (rate - dividend_yield - 0.5 * vol * vol) * years
    terminal = spot * np.exp(drift + vol * math.sqrt(years) * z)
    if option == "call":
        payoff = np.maximum(terminal - strike, 0.0)
    else:
        payoff = np.maximum(strike - terminal, 0.0)
    discounted = math.exp(-rate * years) * payoff

    if antithetic:
        samples = (discounted[:half] + discounted[half:]) / 2  # pair means are independent
    else:
        samples = discounted
    price = float(np.mean(samples))
    std_error = float(np.std(samples, ddof=1)) / math.sqrt(len(samples))
    return McResult(price, std_error)
