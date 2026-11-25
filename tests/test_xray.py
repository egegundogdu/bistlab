import pytest

from bistlab.funds.xray import concentration, country_of, group_weights, overlap


def test_group_weights_sums_and_sorts() -> None:
    rows = group_weights([("EUR", 0.2), ("USD", 0.3), ("EUR", 0.25), ("TRY", 0.25)])
    assert rows[0] == ("EUR", pytest.approx(0.45))
    assert [label for label, _ in rows] == ["EUR", "USD", "TRY"]


def test_country_of() -> None:
    assert country_of("equity_foreign", "DE000ENER6Y0") == "DE"
    assert country_of("equity_tr", "TRASAHOL91Q5") == "TR"
    assert country_of("corporate_bond", "TRSKCTFK2610") == "TR"
    assert country_of("fx_cash", None) == "Döviz nakit"


def test_concentration_equal_weights() -> None:
    result = concentration([0.25, 0.25, 0.25, 0.25])
    assert result.hhi == pytest.approx(0.25)
    assert result.effective_n == pytest.approx(4)
    assert result.top10 == pytest.approx(1.0)


def test_concentration_normalizes_and_ranks() -> None:
    result = concentration([0.6] + [0.02] * 20)  # toplam 1,0
    assert result.top10 == pytest.approx(0.6 + 9 * 0.02)
    assert result.effective_n < 3


def test_overlap() -> None:
    a = {"X": 0.5, "Y": 0.3, "Z": 0.2}
    b = {"X": 0.1, "Y": 0.6, "Q": 0.3}
    assert overlap(a, b) == pytest.approx(0.1 + 0.3)
    assert overlap(a, a) == pytest.approx(1.0)
    assert overlap(a, {"Q": 1.0}) == 0.0
