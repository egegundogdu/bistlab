import pytest
from api_fake import FakeSource

from bistlab.api import core


def test_credit_scores_rows_and_skip() -> None:
    out = core.credit_scores(FakeSource(), ["ASELS", "THYAO", "YOK"])
    assert [c.ticker for c in out.results] == ["ASELS", "THYAO"]
    assert out.skipped == ["YOK"]
    assert len(out.results[0].rows) == 2
    assert out.results[1].currency == "USD"


def test_merton_returns_probability_and_converts_usd_debt() -> None:
    source = FakeSource()
    out = core.merton(source, ["ASELS", "THYAO", "YOK"], 0.40)
    by = {c.ticker: c for c in out.results}
    assert set(by) == {"ASELS", "THYAO"} and out.skipped == ["YOK"]
    assert 0 <= by["ASELS"].default_probability <= 1
    fx = source.latest_fx("USD")
    assert by["THYAO"].default_point == pytest.approx((12e9 + 0.5 * 33e9) / 40 * fx)


def test_multiples_and_median() -> None:
    out = core.multiples(FakeSource(), ["ASELS", "THYAO"])
    assert {r.ticker for r in out.results} == {"ASELS", "THYAO"}
    assert set(out.median) == {"pe", "pb", "ev_ebitda", "fcf_yield"}
    assert all(r.pe is None or r.pe > 0 for r in out.results)


def test_governance_without_files_is_empty() -> None:
    out = core.governance(FakeSource())
    assert out.results == [] and out.skipped == []


def test_multiples_median_uses_universe() -> None:
    """?tickers=THYAO çağrısında medyan tek şirkete değil akran evrenine ait olmalı."""
    full = core.multiples(FakeSource(), ["ASELS", "THYAO"])
    one = core.multiples(FakeSource(), ["THYAO"], universe=["ASELS", "THYAO"])
    assert [r.ticker for r in one.results] == ["THYAO"]
    assert one.median == full.median
