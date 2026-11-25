"""Cox-Ross-Rubinstein binom ağacı: Avrupa ve Amerikan tipi opsiyon fiyatlama."""

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
    """CRR ağacı: u = e^(σ√Δt), d = 1/u, risk-nötr olasılık p = (e^((r-q)Δt) - d) / (u - d).

    Amerikan tipte her düğümde erken kullanım değeri ile devam değerinin büyüğü alınır.
    """
    if steps < 1:
        raise ValueError("Adım sayısı en az 1 olmalı.")
    if spot <= 0 or strike <= 0 or years <= 0 or vol <= 0:
        raise ValueError("Spot, kullanım fiyatı, vade ve volatilite pozitif olmalı.")
    dt = years / steps
    up = math.exp(vol * math.sqrt(dt))
    down = 1 / up
    p = (math.exp((rate - dividend_yield) * dt) - down) / (up - down)
    if not 0 < p < 1:
        raise ValueError("Risk-nötr olasılık (0, 1) dışında; adım sayısını artır.")
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
