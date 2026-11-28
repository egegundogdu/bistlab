import pytest
from api_fake import FakeSource

from bistlab.api import tools


def test_option_report_is_internally_consistent() -> None:
    out = tools.option_report(100.0, 100.0, 90, 0.40, 0.35, "call", 0.0)
    assert abs(out.put_call_parity_gap) < 1e-8
    assert out.binomial_european == pytest.approx(out.black_scholes, abs=0.05)
    assert out.binomial_american >= out.binomial_european - 1e-9
    assert out.monte_carlo == pytest.approx(out.black_scholes, abs=4 * out.monte_carlo_std_error)
    assert 0 < out.greeks.delta < 1
    put = tools.option_report(100.0, 100.0, 90, 0.40, 0.35, "put", 0.0)
    assert (
        put.binomial_american > put.binomial_european
    )  # early exercise has value at positive rates


def test_implied_vol_round_trip() -> None:
    price = tools.option_report(100.0, 110.0, 60, 0.40, 0.30, "call", 0.0).black_scholes
    out = tools.implied_vol(price, 100.0, 110.0, 60, 0.40, "call", 0.0)
    assert out.implied_vol == pytest.approx(0.30, abs=1e-4)


def test_futures_hedge() -> None:
    out = tools.futures_hedge(
        FakeSource(), ["THYAO", "ASELS"], "XU100", 1_000_000, 60, 0.40, 0.0, 1, 10.0
    )
    assert out.hedge_ratio > 0 and out.futures_price > out.spot
    assert out.implied_rate == pytest.approx(0.40, abs=1e-6)
    assert out.contracts is not None and out.hedged_vol < out.unhedged_vol


def test_fund_xray_and_overlap() -> None:
    out = tools.fund_xray(FakeSource(), "IKP", 2, "KVT")
    assert out.holdings == 4 and out.non_try_share == pytest.approx(0.40)
    assert out.risk is not None
    assert out.overlap is not None and [r.asset for r in out.overlap.common] == ["THYAO"]
    with pytest.raises(KeyError):
        tools.fund_xray(FakeSource(), "YOK", 2, None)
