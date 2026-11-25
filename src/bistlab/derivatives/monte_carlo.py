"""Monte Carlo ile Avrupa tipi opsiyon fiyatlama (karşıt değişkenli varyans azaltma)."""

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
        """Varsayılan %95 güven aralığı."""
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
    """Vadedeki fiyatı geometrik Brown hareketiyle simüle eder, ödemeyi iskonto edip ortalar.

    Karşıt değişkenler: her z için -z de kullanılır; bu, aynı yol sayısında hatayı azaltır.
    """
    if paths < 2:
        raise ValueError("En az 2 yol gerekli.")
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
        samples = (discounted[:half] + discounted[half:]) / 2  # çift ortalamaları bağımsızdır
    else:
        samples = discounted
    price = float(np.mean(samples))
    std_error = float(np.std(samples, ddof=1)) / math.sqrt(len(samples))
    return McResult(price, std_error)
