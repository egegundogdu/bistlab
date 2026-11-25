"""KAP 'Portföy Dağılım Raporu' PDF'inden fon varlıklarını çıkarır."""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from sqlalchemy import delete
from sqlalchemy.orm import Session

from bistlab.data.db import FundHolding, get_engine, init_db
from bistlab.funds.tefas import get_or_create_fund

CURRENCIES = {"TL", "TRY", "USD", "EUR", "GBP", "CHF", "JPY", "AUD", "CAD", "SEK", "NOK", "DKK"}

# Bölüm başlığı -> varlık türü. Alt başlık (ör. "Hisse Yabancı") ana başlığı ezer.
SECTIONS = {
    "HİSSE SENETLERİ": "equity",
    "BORÇLANMA SENETLERİ": "debt",
    "T.REPO": "reverse_repo",
    "VIOP Nakit Teminatı": "derivative_margin",
    "MEVDUAT": "deposit",
    "DİĞER": "other",
}
SUBSECTIONS = {
    "Hisse Türk": "equity_tr",
    "Hisse Yabancı": "equity_foreign",
    "Bono": "commercial_paper",
    "Özel Sektör": "corporate_bond",
    "Devlet Tahvili": "government_bond",
    "Hazine Bonosu": "treasury_bill",
    "Y.Fonu Türk": "fund_tr",
    "Y.Fonu Yabancı": "fund_foreign",
    "Döviz": "fx_cash",
}

# Raporlar iki biçimde gelebiliyor: 1,234.56 (İş Portföy) ya da 1.234,56 (Ak Portföy).
AMOUNT = r"-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2}"
PERCENT = r"-?\d+[.,]\d{2}"
ROW_END = re.compile(rf"\s(?P<value>{AMOUNT})\s+{PERCENT}\s+{PERCENT}(?:\s+{PERCENT})?\s*$")
ISIN = re.compile(r"\b([A-Z]{2}[A-Z0-9]{9}\d)\b")
NAV = re.compile(rf"Net Varlık Değeri\s*:\s*({AMOUNT})")
PORTFOLIO = re.compile(rf"^FON PORTFÖY DEĞERİ\s+({AMOUNT})")


@dataclass(frozen=True)
class Holding:
    asset: str
    asset_type: str
    currency: str | None
    isin: str | None
    market_value: float


@dataclass(frozen=True)
class FundReport:
    fund_code: str
    nav: float
    portfolio_value: float
    holdings: list[Holding]

    def weight(self, holding: Holding) -> float:
        """Fon toplam değerine (NAV) göre ağırlık, 0-1."""
        return holding.market_value / self.nav


def to_number(text: str) -> float:
    """Son ayraç ondalık ayracıdır: '1,234.56' ve '1.234,56' -> 1234.56."""
    if text.rfind(",") > text.rfind("."):
        return float(text.replace(".", "").replace(",", "."))
    return float(text.replace(",", ""))


def split_code(line: str, previous: str) -> tuple[str, str | None]:
    """Satırın başındaki kodu ve para birimini ayırır."""
    tokens = line.split()
    if len(tokens) > 1 and tokens[1] in CURRENCIES:  # "ARASE TL", "AUD AUD"
        return tokens[0], tokens[1]
    for m in re.finditer(r"\s([A-Z]{2,3})\b", line):
        if m.group(1) in CURRENCIES:
            return line[: m.start()].strip(), m.group(1)
    if tokens and tokens[0] in CURRENCIES:  # kod bir önceki satıra taşmış
        return previous.strip(), tokens[0]
    return re.split(r"\s+[\d,]+\.\d", line)[0].strip(), None


def normalize_currency(currency: str | None) -> str | None:
    return "TRY" if currency == "TL" else currency


def clean_code(code: str) -> str:
    return code.removesuffix(" EQUITY").strip()


def parse_report(text: str) -> FundReport:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    fund_code = lines[0].split("-")[0].strip()
    nav_match = NAV.search(text)
    if nav_match is None:
        raise ValueError("Net varlık değeri bulunamadı")
    nav = to_number(nav_match.group(1))

    holdings: list[Holding] = []
    portfolio_value: float | None = None
    in_table = False
    asset_type = "other"
    previous = ""
    for line in lines:
        if line.startswith("III-FON PORTFÖY"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("IV-"):
            break
        if (m := PORTFOLIO.match(line)) is not None:
            portfolio_value = to_number(m.group(1))
            continue
        if line.startswith("GRUP TOPLAMI"):
            continue
        row = ROW_END.search(line)
        if row is None:
            if line in SECTIONS:
                asset_type = SECTIONS[line]
            elif line in SUBSECTIONS:
                asset_type = SUBSECTIONS[line]
            previous = line
            continue
        code, currency = split_code(line[: row.start()], previous)
        if asset_type.startswith("fund"):  # "ALE AKPORTFÖY TL" -> "ALE"
            code = code.split()[0]
        isin = ISIN.search(line)
        holdings.append(
            Holding(
                asset=clean_code(code),
                asset_type=asset_type,
                currency=normalize_currency(currency),
                isin=isin.group(1) if isin else None,
                market_value=to_number(row["value"]),
            )
        )
        previous = line

    if portfolio_value is None:
        raise ValueError("Fon portföy değeri satırı bulunamadı")
    # Döviz kalemleri raporda "hazır değerler"e sayılır, portföy değerine girmez.
    total = sum(h.market_value for h in holdings if h.asset_type != "fx_cash")
    if abs(total - portfolio_value) > 0.0001 * portfolio_value:
        raise ValueError(f"Kalemler toplamı {total:,.2f} != portföy {portfolio_value:,.2f}")
    return FundReport(fund_code, nav, portfolio_value, holdings)


def extract_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def month_end(period: str) -> dt.date:
    """'2026-10' -> 2026-10-31"""
    year, month = (int(part) for part in period.split("-"))
    return dt.date(year, month, calendar.monthrange(year, month)[1])


def save_holdings(session: Session, report: FundReport, report_date: dt.date) -> int:
    """Aynı fon+tarih için eski kayıtları silip yenilerini yazar."""
    fund = get_or_create_fund(session, report.fund_code)
    session.flush()
    session.execute(
        delete(FundHolding).where(
            FundHolding.fund_id == fund.id, FundHolding.report_date == report_date
        )
    )
    merged: dict[str, list[Holding]] = defaultdict(list)
    for holding in report.holdings:
        merged[holding.asset].append(holding)
    for asset, items in merged.items():
        value = sum(h.market_value for h in items)
        first = items[0]
        session.add(
            FundHolding(
                fund_id=fund.id,
                report_date=report_date,
                asset=asset,
                asset_type=first.asset_type,
                weight=value / report.nav,
                market_value=value,
                currency=first.currency,
                isin=first.isin,
            )
        )
    return len(merged)


def main() -> None:
    parser = argparse.ArgumentParser(description="KAP portföy dağılım raporunu içe aktar")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--period", required=True, help="Rapor ayı, ör. 2026-10")
    args = parser.parse_args()

    report = parse_report(extract_text(args.pdf))
    report_date = month_end(args.period)
    engine = get_engine()
    init_db(engine)
    with Session(engine) as session:
        count = save_holdings(session, report, report_date)
        session.commit()

    by_type: dict[str, float] = defaultdict(float)
    for holding in report.holdings:
        by_type[holding.asset_type] += report.weight(holding)
    print(f"{report.fund_code} {report_date}: {count} kalem, NAV {report.nav:,.0f} TL")
    for asset_type, weight in sorted(by_type.items(), key=lambda item: -item[1]):
        print(f"  {asset_type:<18} %{weight * 100:6.2f}")
    print(f"  {'TOPLAM':<18} %{sum(by_type.values()) * 100:6.2f}")
    print("En büyük 10:")
    for holding in sorted(report.holdings, key=lambda h: -h.market_value)[:10]:
        print(f"  {holding.asset:<16} %{report.weight(holding) * 100:5.2f}")


if __name__ == "__main__":
    main()
