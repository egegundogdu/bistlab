import datetime as dt
import math

import pytest

from bistlab.real.view import (
    annualize,
    cpi_for,
    fcf_yield,
    performance,
    restatement_factor,
    value_asof,
)

D = dt.date
CPI = {D(2025, 1, 1): 100.0, D(2025, 6, 1): 120.0, D(2025, 12, 1): 150.0, D(2026, 10, 1): 200.0}


def test_cpi_for_uses_month_and_flags_unpublished_month() -> None:
    assert cpi_for(CPI, D(2025, 6, 17)) == (120.0, False)
    assert cpi_for(CPI, D(2026, 11, 24)) == (200.0, True)
    with pytest.raises(KeyError):
        cpi_for(CPI, D(2024, 3, 5))


def test_value_asof() -> None:
    points = [(D(2025, 1, 2), 30.0), (D(2025, 1, 6), 31.0)]
    assert value_asof(points, D(2025, 1, 5)) == 30.0
    assert value_asof(points, D(2025, 1, 6)) == 31.0
    assert value_asof(points, D(2025, 1, 1)) is None


def test_performance_real_and_usd() -> None:
    prices = [(D(2025, 1, 2), 10.0), (D(2025, 12, 31), 30.0)]
    usd = [(D(2025, 1, 2), 30.0), (D(2025, 12, 31), 45.0)]
    p = performance("TEST", prices, CPI, usd)
    assert p.nominal == pytest.approx(2.0)
    assert p.real == pytest.approx(3.0 * 100 / 150 - 1)  # %100 reel
    assert p.usd == pytest.approx((30 / 45) / (10 / 30) - 1)  # %100 USD
    assert not p.cpi_estimated


def test_annualize() -> None:
    assert annualize(0.21, 2.0) == pytest.approx(0.1)
    assert math.isnan(annualize(0.1, 0.0))


def test_restatement_and_fcf_yield() -> None:
    assert restatement_factor(D(2025, 12, 31), CPI) == pytest.approx(200 / 150)
    tl = fcf_yield("A", "TRY", D(2025, 12, 31), 10e9, 1e9, 100.0, 1.0, CPI)
    assert tl.nominal_yield == pytest.approx(0.1)
    assert tl.restated_yield == pytest.approx(0.1 * 200 / 150)
    usd = fcf_yield("B", "USD", D(2025, 12, 31), 1e9, 1e9, 420.0, 42.0, CPI)
    assert usd.market_cap == pytest.approx(10e9)
    assert usd.factor == 1.0 and usd.restated_yield == pytest.approx(0.1)
