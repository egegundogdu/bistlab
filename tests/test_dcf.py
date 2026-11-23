import pytest

from bistlab.valuation.dcf import (
    capm_cost_of_equity,
    dcf_value,
    fisher_real_rate,
    present_value,
    sensitivity_table,
    terminal_value,
    wacc,
)


def test_capm() -> None:
    # %30 risksiz + 1,2 × %6 prim = %37,2
    assert capm_cost_of_equity(0.30, 1.2, 0.06) == pytest.approx(0.372)


def test_wacc_applies_tax_shield_to_debt() -> None:
    # 0,6 × %37 + 0,4 × %40 × (1 - 0,25) = %22,2 + %12 = %34,2
    assert wacc(60, 40, 0.37, 0.40, 0.25) == pytest.approx(0.342)


def test_fisher_real_rate() -> None:
    # 1,40 / 1,30 - 1 ≈ %7,69
    assert fisher_real_rate(0.40, 0.30) == pytest.approx(0.0769230769)


def test_present_value() -> None:
    # 110 / 1,1 + 121 / 1,21 = 100 + 100
    assert present_value([110, 121], 0.10) == pytest.approx(200)


def test_terminal_value_requires_rate_above_growth() -> None:
    assert terminal_value(121, 0.10, 0.0) == pytest.approx(1210)
    with pytest.raises(ValueError):
        terminal_value(121, 0.05, 0.05)


def test_dcf_value_end_to_end() -> None:
    # PV(akışlar) = 200, TV = 1210, PV(TV) = 1210 / 1,21 = 1000, FD = 1200
    result = dcf_value([110, 121], 0.10, 0.0, net_debt=200, shares=10)
    assert result.enterprise_value == pytest.approx(1200)
    assert result.equity_value == pytest.approx(1000)
    assert result.per_share == pytest.approx(100)
    assert result.terminal_share == pytest.approx(1000 / 1200)


def test_sensitivity_value_falls_as_rate_rises() -> None:
    table = sensitivity_table([110, 121], 200, 10, rates=[0.08, 0.10, 0.12], growths=[0.0, 0.02])
    assert table.shape == (3, 2)
    column = list(table[0.0])
    assert column == sorted(column, reverse=True)
