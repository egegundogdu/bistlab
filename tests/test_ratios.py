import pytest

from bistlab.valuation.ratios import cagr, current_ratio


def test_current_ratio() -> None:
    assert current_ratio(150, 100) == pytest.approx(1.5)


def test_current_ratio_rejects_zero_liabilities() -> None:
    with pytest.raises(ValueError):
        current_ratio(150, 0)


def test_cagr_doubling_in_one_year() -> None:
    assert cagr(100, 200, 1) == pytest.approx(1.0)


def test_cagr_three_years() -> None:
    assert cagr(100, 133.1, 3) == pytest.approx(0.10)
