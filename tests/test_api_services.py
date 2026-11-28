import datetime as dt

import pytest
from api_fake import TODAY, FakeSource

from bistlab.api import services


def test_quality_report_counts_and_filter() -> None:
    report = services.quality_report(FakeSource())
    assert sum(report.summary.values()) == 3
    only = services.quality_report(FakeSource(), issues_only=True)
    assert all(s.status != "Good" for s in only.series)


def test_real_returns_includes_market_and_skips_unknown() -> None:
    out = services.real_returns(FakeSource(), ["THYAO", "YOKBOYLE"], dt.date(2023, 1, 2))
    assert [r.ticker for r in out.results] == ["XU100", "THYAO"]
    assert out.skipped == ["YOKBOYLE"]
    assert out.cpi_change is not None and out.cpi_change > 0
    assert out.results[0].real < out.results[0].nominal  # enflasyon pozitif


def test_real_fcf_usd_factor_is_one() -> None:
    out = services.real_fcf(FakeSource(), ["THYAO", "ASELS", "YOK"])
    by = {r.ticker: r for r in out.results}
    assert by["THYAO"].factor == 1.0
    assert by["ASELS"].factor > 1.0
    assert out.skipped == ["YOK"]


def test_macro_stress_shapes() -> None:
    out = services.macro_stress(FakeSource(), ["THYAO", "ASELS"], 2.0, 5, TODAY)
    assert {b.ticker for b in out.betas} == {"THYAO", "ASELS"}
    assert len(out.scenarios) == 3 and out.scenarios[0].portfolio is not None
    since = TODAY - dt.timedelta(days=round(365.25 * 2))
    assert out.historical.in_sample == (out.historical.start >= since)
    assert len(out.historical.rows) == 2
    assert out.fx_shock_out_of_sample


def test_missing_macro_raises_data_unavailable() -> None:
    with pytest.raises(services.DataUnavailable):
        services.real_returns(FakeSource(with_macro=False), ["THYAO"], dt.date(2023, 1, 2))
