import datetime as dt

import pytest

from bistlab.funds.kap_report import month_end, parse_report

SAMPLE = """\
XYZ-ÖRNEK KARMA FON
I-FONU TANITICI BİLGİLER
D-)Toplam Değer/Net Varlık Değeri : 1,000.00
III-FON PORTFÖY DEĞERİ TABLOSU
HİSSE SENETLERİ
Hisse Türk
DOĞU ARAS ENERJİ
ARASE TL TREARAS00039 10.00 81.42 30/06/26 8010051 70.000000 500.00 50.00 50.00 50.00
YATIRIMLARI A.Ş.
GRUP TOPLAMI 10.00 500.00 50.00 50.00 50.00
Hisse Yabancı
ENGI FP EQUITY EUR ENGIE FR0010208488 1.00 20.63 18/06/26 23.37 200.00 20.00 20.00 20.00
FORTUM FH
EUR FORTUM OYJ FI0009007132 1.00 16.79 18/06/26 22.96 100.00 10.00 10.00 10.00
EQUITY
GRUP TOPLAMI 2.00 300.00 30.00 30.00 30.00
VIOP Nakit Teminatı
VIOP Nakit Teminatı 150.00 150.00 100.00 15.00
DİĞER
Döviz
USD USD FED USD 1.00 49.53 30/10/26 49.77 40.00 0.00 0.00 4.00
FON PORTFÖY DEĞERİ 950.00 100.00
IV-FON TOPLAM DEĞERİ TABLOSU
A-)FON PORTFÖY DEĞERİ 950.00 95.00 %
"""


def test_parse_report_reads_header_and_rows() -> None:
    report = parse_report(SAMPLE)
    assert report.fund_code == "XYZ"
    assert report.nav == 1000.0
    assert report.portfolio_value == 950.0
    assert [h.asset for h in report.holdings] == [
        "ARASE",
        "ENGI FP",
        "FORTUM FH",
        "VIOP Nakit Teminatı",
        "USD",
    ]


def test_asset_types_currencies_and_isin() -> None:
    holdings = {h.asset: h for h in parse_report(SAMPLE).holdings}
    assert holdings["ARASE"].asset_type == "equity_tr"
    assert holdings["ARASE"].currency == "TRY"
    assert holdings["ARASE"].isin == "TREARAS00039"
    assert holdings["FORTUM FH"].asset_type == "equity_foreign"
    assert holdings["FORTUM FH"].currency == "EUR"
    assert holdings["VIOP Nakit Teminatı"].asset_type == "derivative_margin"
    assert holdings["USD"].asset_type == "fx_cash"


def test_weights_use_nav() -> None:
    report = parse_report(SAMPLE)
    weights = {h.asset: report.weight(h) for h in report.holdings}
    assert weights["ARASE"] == pytest.approx(0.5)
    assert sum(weights.values()) == pytest.approx(0.99)


def test_total_mismatch_raises() -> None:
    broken = SAMPLE.replace("FON PORTFÖY DEĞERİ 950.00", "FON PORTFÖY DEĞERİ 999.00")
    with pytest.raises(ValueError, match="Sum of items"):
        parse_report(broken)


def test_month_end() -> None:
    assert month_end("2026-10") == dt.date(2026, 10, 31)
    assert month_end("2028-02") == dt.date(2028, 2, 29)
