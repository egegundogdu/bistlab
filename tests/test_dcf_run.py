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


def test_lease_adjusted_defaults_to_false() -> None:
    assert parse(_data("USD")).lease_adjusted is False


def test_adjust_for_leases() -> None:
    import datetime as dt

    import pandas as pd

    from bistlab.valuation.run import adjust_for_leases

    index = [dt.date(2024, 12, 31), dt.date(2025, 12, 31)]
    items = pd.DataFrame(
        {"Current Capital Lease Obligation": [2.0, 4.0], "Capital Lease Obligations": [10.0, 12.0]},
        index=index,
    )
    fcf, debt = adjust_for_leases(items, base_fcf=10.0, total_debt=20.0, years=2)
    assert fcf == pytest.approx(7.0)  # 10 - ortalama(2, 4)
    assert debt == pytest.approx(8.0)  # 20 - son kira yükümlülüğü 12


def test_implied_growth_roundtrip() -> None:
    from bistlab.valuation.dcf import dcf_value
    from bistlab.valuation.run import implied_growth

    flows = project_cash_flows(100, [0.15] * 5)
    target = dcf_value(flows, 0.12, 0.03, 200, 10).per_share
    assert implied_growth(100, 5, 0.12, 0.03, 200, 10, target) == pytest.approx(0.15, abs=1e-4)


def test_implied_growth_none_for_negative_fcf() -> None:
    from bistlab.valuation.run import implied_growth

    assert implied_growth(-5, 5, 0.12, 0.03, 0, 10, 50) is None
