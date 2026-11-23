"""TCMB EVDS3 web servisinden makro veri çekme ve veritabanına yazma."""

from __future__ import annotations

import argparse
import datetime as dt
import os
from typing import Any

import httpx
from sqlalchemy.orm import Session

from bistlab.data.db import MacroObservation, get_engine, init_db

BASE_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis"

# EVDS3 tek istekte yaklaşık 1.000 günden fazlasını sessizce kesiyor;
# bu yüzden uzun aralıkları yıllık parçalar hâlinde istiyoruz.
MAX_DAYS_PER_REQUEST = 365

Observation = tuple[dt.date, float]


def build_url(code: str, start: dt.date, end: dt.date) -> str:
    """Tek seri için EVDS3 istek adresini kurar. Anahtar URL'de değil, başlıkta gider."""
    return f"{BASE_URL}/series={code}&startDate={start:%d-%m-%Y}&endDate={end:%d-%m-%Y}&type=json"


def date_windows(
    start: dt.date, end: dt.date, max_days: int = MAX_DAYS_PER_REQUEST
) -> list[tuple[dt.date, dt.date]]:
    """[start, end] aralığını en fazla max_days günlük, çakışmayan parçalara böler."""
    windows: list[tuple[dt.date, dt.date]] = []
    current = start
    while current <= end:
        window_end = min(current + dt.timedelta(days=max_days - 1), end)
        windows.append((current, window_end))
        current = window_end + dt.timedelta(days=1)
    return windows


def parse_evds_date(text: str) -> dt.date:
    """EVDS tarihini çevirir: '15-01-2026' (günlük) ya da '2026-1' (aylık, ayın ilk günü)."""
    parts = text.split("-")
    if len(parts) == 3:
        day, month, year = (int(p) for p in parts)
        return dt.date(year, month, day)
    if len(parts) == 2:
        year, month = (int(p) for p in parts)
        return dt.date(year, month, 1)
    raise ValueError(f"Tanınmayan EVDS tarih biçimi: {text!r}")


def parse_items(payload: dict[str, Any], code: str) -> list[Observation]:
    """EVDS cevabından (tarih, değer) çiftlerini çıkarır; boş değerleri atlar."""
    column = code.replace(".", "_")
    rows: list[Observation] = []
    for item in payload.get("items", []):
        value = item.get(column)
        if value in (None, ""):
            continue
        rows.append((parse_evds_date(item["Tarih"]), float(value)))
    return rows


def deduplicate(rows: list[Observation]) -> list[Observation]:
    """Aynı tarih birden fazla gelirse sonuncuyu tutar ve tarihe göre sıralar."""
    return sorted(dict(rows).items())


def fetch_series(code: str, start: dt.date, end: dt.date, api_key: str) -> list[Observation]:
    """Bir seriyi parça parça EVDS3'ten çeker (internet ve API anahtarı gerekir)."""
    rows: list[Observation] = []
    with httpx.Client(headers={"key": api_key}, timeout=30) as client:
        for window_start, window_end in date_windows(start, end):
            response = client.get(build_url(code, window_start, window_end))
            response.raise_for_status()
            rows.extend(parse_items(response.json(), code))
        return deduplicate(rows)


def save_series(session: Session, code: str, rows: list[Observation]) -> int:
    """Gözlemleri yazar; aynı tarih varsa günceller. Yazılan satır sayısını döner."""
    for date, value in rows:
        session.merge(MacroObservation(code=code, date=date, value=value))
    session.commit()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="EVDS serilerini çekip veritabanına yazar.")
    parser.add_argument("codes", nargs="+", help="Seri kodları, ör. TP.DK.USD.A.YTL")
    parser.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2020, 1, 1))
    args = parser.parse_args()

    engine = get_engine()
    api_key = os.environ.get("EVDS_API_KEY")
    if not api_key:
        raise RuntimeError("EVDS_API_KEY tanımlı değil. .env dosyasını kontrol et.")

    init_db(engine)
    with Session(engine) as session:
        for code in args.codes:
            rows = fetch_series(code, args.start, dt.date.today(), api_key)
            count = save_series(session, code, rows)
            print(f"{code}: {count} gözlem kaydedildi")


if __name__ == "__main__":
    main()
