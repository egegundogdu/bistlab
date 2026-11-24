from typing import Any

import pytest

from bistlab.valuation.assumptions import parse
from bistlab.valuation.dcf import blume_adjust, convert_rate
from bistlab.valuation.run import cost_of_capital, project_cash_flows, terminal_growth


def _data(currency: str) -> dict[str, Any]:
    return {
        "company": {"ticker": "test", "currency": currency},
        "market": {
            "usd_risk_free": 0.04,
            "equity_risk_premium": 0.09,
            "us_inflation": 0.02,
            "local_inflation": 0.20,
        },
        "capital": {"pre_tax_cost_of_debt": 0.40, "tax_rate": 0.25},
        "forecast": {"growth": [0.10, 0.10], "terminal_real_growth": 0.02},
    }


def test_parse_defaults() -> None:
    a = parse(_data("try"))
    assert a.ticker == "TEST" and a.currency == "TRY"
    assert a.beta_override is None and a.use_blume is True
    assert a.base_fcf_years == 1 and a.growth == (0.10, 0.10)


def test_convert_rate_and_blume() -> None:
    assert convert_rate(0.13, 0.02, 0.20) == pytest.approx(1.13 * 1.20 / 1.02 - 1)
    assert blume_adjust(1.0) == pytest.approx(1.0)
    assert blume_adjust(0.5) == pytest.approx(0.665)


def test_cost_of_capital_usd_and_try() -> None:
    ke_usd, wacc_usd = cost_of_capital(parse(_data("USD")), 100, 0, 1.0)
    assert ke_usd == pytest.approx(0.13) and wacc_usd == pytest.approx(0.13)
    ke_try, _ = cost_of_capital(parse(_data("TRY")), 100, 0, 1.0)
    assert ke_try == pytest.approx(1.13 * 1.20 / 1.02 - 1)


def test_terminal_growth_uses_currency_inflation() -> None:
    assert terminal_growth(parse(_data("TRY"))) == pytest.approx(1.02 * 1.20 - 1)
    assert terminal_growth(parse(_data("USD"))) == pytest.approx(1.02 * 1.02 - 1)


def test_project_cash_flows() -> None:
    assert project_cash_flows(100, [0.10, 0.10]) == pytest.approx([110, 121])
