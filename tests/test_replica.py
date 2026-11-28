import datetime as dt

import pytest

from bistlab.funds.replica import (
    Position,
    cash_return,
    period_return,
    replica_return,
    to_tl,
    value_on,
)

D = dt.date
SERIES = [(D(2026, 10, 30), 100.0), (D(2026, 11, 3), 110.0), (D(2026, 11, 20), 121.0)]


def test_value_on_uses_last_known_value() -> None:
    assert value_on(SERIES, D(2026, 10, 31)) == 100.0  # weekend -> previous day
    assert value_on(SERIES, D(2026, 11, 25)) == 121.0
    assert value_on(SERIES, D(2026, 10, 1)) is None


def test_period_return() -> None:
    assert period_return(SERIES, D(2026, 10, 31), D(2026, 11, 20)) == pytest.approx(0.21)
    assert period_return(SERIES, D(2026, 10, 1), D(2026, 11, 20)) is None


def test_to_tl_compounds_fx() -> None:
    # Hisse yerel parada %10, kur %5 -> TL'de %15,5
    assert to_tl(0.10, 0.05) == pytest.approx(0.155)


def test_cash_return() -> None:
    assert cash_return(0.40, 365) == pytest.approx(0.40)
    assert cash_return(0.40, 0) == 0.0


def test_replica_rescales_missing_positions() -> None:
    positions = [
        Position("A", 0.5, 0.10),
        Position("B", 0.3, -0.10),
        Position("C", 0.2, None),  # veri yok
    ]
    result = replica_return(positions)
    assert result.covered_weight == pytest.approx(0.8)
    assert result.portfolio_return == pytest.approx((0.05 - 0.03) / 0.8)
    assert result.contributions[0][0] == "B"  # worst first


def test_replica_without_data_raises() -> None:
    with pytest.raises(ValueError):
        replica_return([Position("A", 1.0, None)])
