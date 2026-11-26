import pytest
from api_fake import FakeSource

from bistlab.api import core


def test_dcf_try_and_usd() -> None:
    tr = core.dcf(FakeSource(), "ASELS")
    assert tr.currency == "TRY" and tr.per_share_try > 0
    assert tr.wacc == tr.model_wacc and tr.wacc > tr.terminal_growth
    assert len(tr.sensitivity) == 5 and len(tr.sensitivity[0]) == 3
    assert tr.sensitivity[2][1] == pytest.approx(tr.per_share_try)
    usd = core.dcf(FakeSource(), "THYAO")
    assert usd.currency == "USD" and usd.per_share_try > 0


def test_dcf_overrides_move_value_the_right_way() -> None:
    base = core.dcf(FakeSource(), "ASELS")
    higher_rate = core.dcf(FakeSource(), "ASELS", wacc=base.wacc + 0.02)
    higher_g = core.dcf(FakeSource(), "ASELS", terminal_growth=base.terminal_growth + 0.01)
    assert higher_rate.per_share_try < base.per_share_try < higher_g.per_share_try


def test_dcf_errors() -> None:
    with pytest.raises(KeyError):
        core.dcf(FakeSource(), "BIMAS")
    with pytest.raises(ValueError):
        core.dcf(FakeSource(), "ASELS", wacc=0.10, terminal_growth=0.20)
