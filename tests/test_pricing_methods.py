import pytest

from bistlab.derivatives.binomial import binomial_price
from bistlab.derivatives.black_scholes import bs_price
from bistlab.derivatives.monte_carlo import monte_carlo_price

ARGS = (42.0, 40.0, 0.5, 0.10, 0.20)  # Hull example: spot, strike, maturity, rate, vol


def test_binomial_converges_to_black_scholes() -> None:
    for option in ("call", "put"):
        tree = binomial_price(*ARGS, option, steps=2000)  # type: ignore[arg-type]
        assert tree == pytest.approx(bs_price(*ARGS, option), abs=0.005)  # type: ignore[arg-type]


def test_american_put_is_worth_more_than_european() -> None:
    args = (100.0, 100.0, 1.0, 0.30, 0.30)  # high rates: early exercise is valuable
    european = binomial_price(*args, "put", steps=500)
    american = binomial_price(*args, "put", steps=500, american=True)
    assert american > european + 0.5


def test_american_call_without_dividends_equals_european() -> None:
    european = binomial_price(*ARGS, "call", steps=500)
    american = binomial_price(*ARGS, "call", steps=500, american=True)
    assert american == pytest.approx(european, abs=1e-9)


def test_monte_carlo_brackets_black_scholes() -> None:
    for option in ("call", "put"):
        mc = monte_carlo_price(*ARGS, option, paths=200_000)  # type: ignore[arg-type]
        exact = bs_price(*ARGS, option)  # type: ignore[arg-type]
        assert abs(mc.price - exact) < 3 * mc.std_error
        low, high = mc.confidence_interval(z=3.0)
        assert low < exact < high


def test_antithetic_variates_reduce_error() -> None:
    plain = monte_carlo_price(*ARGS, "call", paths=20_000, antithetic=False)
    anti = monte_carlo_price(*ARGS, "call", paths=20_000, antithetic=True)
    assert anti.std_error < plain.std_error


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError):
        binomial_price(*ARGS, "call", steps=0)
    with pytest.raises(ValueError):
        monte_carlo_price(*ARGS, "call", paths=1)
