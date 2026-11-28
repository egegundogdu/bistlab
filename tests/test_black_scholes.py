import math

import pytest

from bistlab.derivatives.black_scholes import bs_price, greeks, implied_volatility

HULL = {"spot": 42.0, "strike": 40.0, "years": 0.5, "rate": 0.10, "vol": 0.20}


def test_hull_textbook_example() -> None:
    # Hull, Options, Futures and Other Derivatives: c ≈ 4,76, p ≈ 0,81
    assert bs_price(**HULL, option="call") == pytest.approx(4.76, abs=0.005)
    assert bs_price(**HULL, option="put") == pytest.approx(0.81, abs=0.005)


def test_put_call_parity_with_dividends() -> None:
    s, k, t, r, q = 100.0, 110.0, 0.8, 0.30, 0.04
    call = bs_price(s, k, t, r, 0.35, "call", q)
    put = bs_price(s, k, t, r, 0.35, "put", q)
    assert call - put == pytest.approx(s * math.exp(-q * t) - k * math.exp(-r * t))


def test_greeks_match_finite_differences() -> None:
    base = {"spot": 100.0, "strike": 95.0, "years": 0.75, "rate": 0.05, "vol": 0.30}
    h = 1e-4
    for option in ("call", "put"):
        g = greeks(**base, option=option, dividend_yield=0.02)

        def price(key: str = "spot", bump: float = 0.0, opt: str = option) -> float:
            args = {**base, key: base[key] + bump}
            return bs_price(**args, option=opt, dividend_yield=0.02)  # type: ignore[arg-type]

        def central(key: str) -> float:
            return (price(key, h) - price(key, -h)) / (2 * h)

        assert g.delta == pytest.approx(central("spot"), rel=1e-5)
        gamma = (price("spot", 1e-2) - 2 * price() + price("spot", -1e-2)) / 1e-4
        assert g.gamma == pytest.approx(gamma, rel=1e-3)
        assert g.vega == pytest.approx(central("vol") / 100, rel=1e-5)
        assert g.rho == pytest.approx(central("rate") / 100, rel=1e-5)
        assert g.theta == pytest.approx(-central("years") / 365, rel=1e-5)


def test_implied_volatility_roundtrip() -> None:
    for option in ("call", "put"):
        price = bs_price(50.0, 55.0, 0.4, 0.35, 0.42, option)  # type: ignore[arg-type]
        iv = implied_volatility(price, 50.0, 55.0, 0.4, 0.35, option)  # type: ignore[arg-type]
        assert iv == pytest.approx(0.42, abs=1e-6)


def test_implied_volatility_rejects_arbitrage_prices() -> None:
    with pytest.raises(ValueError):
        implied_volatility(
            60.0, 50.0, 55.0, 0.4, 0.35, "call"
        )  # a call cannot cost more than the stock


def test_expiry_returns_intrinsic_value() -> None:
    assert bs_price(105.0, 100.0, 0.0, 0.3, 0.4, "call") == pytest.approx(5.0)
    assert bs_price(105.0, 100.0, 0.0, 0.3, 0.4, "put") == pytest.approx(0.0)
