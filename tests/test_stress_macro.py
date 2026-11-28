import datetime as dt

import numpy as np
import pandas as pd
import pytest

from bistlab.stress.macro import (
    factor_betas,
    max_weekly_move,
    scenario_impact,
    weekly_returns,
    window_return,
    worst_window,
)


def test_factor_betas_recovers_known_coefficients() -> None:
    rng = np.random.default_rng(0)
    market = rng.normal(0, 0.03, 200)
    fx = rng.normal(0, 0.01, 200)
    y = 0.001 + 1.2 * market + 0.5 * fx + rng.normal(0, 0.001, 200)
    b = factor_betas(y, market, fx)
    assert b.market == pytest.approx(1.2, abs=0.02)
    assert b.fx == pytest.approx(0.5, abs=0.05)
    assert b.r2 > 0.99 and b.n == 200
    assert abs(b.t_fx) > 2 and b.fx_used == b.fx


def test_insignificant_fx_beta_is_zeroed_in_scenarios() -> None:
    rng = np.random.default_rng(1)
    market = rng.normal(0, 0.03, 100)
    fx = rng.normal(0, 0.002, 100)  # small, noisy FX moves
    y = 1.0 * market + rng.normal(0, 0.03, 100)  # no true FX sensitivity
    b = factor_betas(y, market, fx)
    assert abs(b.t_fx) < 2 and b.fx_used == 0.0
    assert scenario_impact(b, -0.2, 0.3) == pytest.approx(b.market * -0.2)


def test_scenario_impact() -> None:
    b = factor_betas(
        np.array([0.0, 1.0, 2.0]), np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0])
    )
    assert scenario_impact(b, -0.2, 0.3) == pytest.approx(b.market * -0.2 + b.fx * 0.3)


def test_worst_window() -> None:
    index = pd.to_datetime(["2025-03-17", "2025-03-18", "2025-03-19", "2025-03-20", "2025-03-21"])
    closes = pd.Series([100.0, 101.0, 90.0, 85.0, 95.0], index=index)
    start, end, change = worst_window(closes, 2)
    assert (start.date(), end.date()) == (dt.date(2025, 3, 18), dt.date(2025, 3, 20))
    assert change == pytest.approx(85 / 101 - 1)


def test_window_return_and_weekly() -> None:
    points = [(dt.date(2025, 1, d), 10.0 + d) for d in (6, 7, 8, 9, 10, 13, 14, 15, 16, 17)]
    assert window_return(points, dt.date(2025, 1, 6), dt.date(2025, 1, 17)) == pytest.approx(
        27 / 16 - 1
    )
    assert window_return(points, dt.date(2024, 12, 31), dt.date(2025, 1, 17)) is None
    weekly = weekly_returns(points)
    assert len(weekly) == 1 and weekly.iloc[0] == pytest.approx(27 / 20 - 1)


def test_max_weekly_move() -> None:
    points = [
        (dt.date(2025, 1, 3), 100.0),
        (dt.date(2025, 1, 10), 104.0),
        (dt.date(2025, 1, 17), 102.0),
    ]
    assert max_weekly_move(points) == pytest.approx(0.04)
