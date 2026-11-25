"""Türkçe sayı biçimli (1.234,56) KAP raporu, Ak Portföy düzeni."""

import pytest

from bistlab.funds.kap_report import parse_report, to_number

SAMPLE = """\
KVT - Ak Portföy Enerji Şirketleri Hisse Senedi (TL) Fonu
Ekim-2026
D-)Toplam Değer/Net Varlık Değeri :
1.000,00
III-FON PORTFÖY DEĞERİ TABLOSU
HİSSE SENETLERİ
Hisse Türk
AHGAZ TL AHGAZ TREAHLA00019 145.000,00 27,48 30/10/26 80100511 46,06 600,00 60,00 60,00 60,00
AHGAZ TL AHGAZ TREAHLA00019 -5.000,00 27,48 30/10/26 80100511 46,06 -100,00 -10,00 -10,00 -10,00
GRUP TOPLAMI 140.000,00 500,00 100,00 50,00 50,00
MEVDUAT
AKBANK T.A.S. TL 02/11/26 0 11,00 875.000,00 30/10/26 300,00 11,000000 300,00 100,00 30,00 30,00
DİĞER
Y.Fonu Türk
ALE AKPORTFÖY TL ALE 457.550,00 14,20 16/10/26 14,45 200,00 100,00 20,00 20,00
FON PORTFÖY DEĞERİ 1.000,00 100,00
IV-FON TOPLAM DEĞERİ TABLOSU
"""


def test_to_number_both_formats() -> None:
    assert to_number("1,234.56") == 1234.56
    assert to_number("1.234,56") == 1234.56
    assert to_number("-230.300,00") == -230300.0
    assert to_number("0,62") == 0.62


def test_parse_turkish_format() -> None:
    report = parse_report(SAMPLE)
    assert report.fund_code == "KVT"
    assert report.nav == 1000.0
    assert report.portfolio_value == 1000.0
    assets = [(h.asset, h.asset_type, h.market_value) for h in report.holdings]
    assert assets == [
        ("AHGAZ", "equity_tr", 600.0),
        ("AHGAZ", "equity_tr", -100.0),
        ("AKBANK T.A.S.", "deposit", 300.0),
        ("ALE", "fund_tr", 200.0),
    ]
    assert sum(report.weight(h) for h in report.holdings) == pytest.approx(1.0)
