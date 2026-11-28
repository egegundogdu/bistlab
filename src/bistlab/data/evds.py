"""Fetches macro data from the CBRT EVDS3 web service into the database."""

from __future__ import annotations

import argparse
import datetime as dt
import os
from typing import Any

import httpx
from sqlalchemy.orm import Session

from bistlab.data.db import MacroObservation, get_engine, init_db

BASE_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis"

# EVDS3 silently truncates a request beyond roughly 1,000 days,
# so long ranges are requested in yearly chunks.
MAX_DAYS_PER_REQUEST = 365

Observation = tuple[dt.date, float]


def build_url(code: str, start: dt.date, end: dt.date) -> str:
    """Builds the EVDS3 URL for one series. The key goes in a header, not the URL."""
    return f"{BASE_URL}/series={code}&startDate={start:%d-%m-%Y}&endDate={end:%d-%m-%Y}&type=json"


def date_windows(
    start: dt.date, end: dt.date, max_days: int = MAX_DAYS_PER_REQUEST
) -> list[tuple[dt.date, dt.date]]:
    """Splits [start, end] into non-overlapping chunks of at most max_days days."""
    windows: list[tuple[dt.date, dt.date]] = []
    current = start
    while current <= end:
        window_end = min(current + dt.timedelta(days=max_days - 1), end)
        windows.append((current, window_end))
        current = window_end + dt.timedelta(days=1)
    return windows


def parse_evds_date(text: str) -> dt.date:
    """Parses an EVDS date: '15-01-2026' (daily) or '2026-1' (monthly, first day)."""
    parts = text.split("-")
    if len(parts) == 3:
        day, month, year = (int(p) for p in parts)
        return dt.date(year, month, day)
    if len(parts) == 2:
        year, month = (int(p) for p in parts)
        return dt.date(year, month, 1)
    raise ValueError(f"Unrecognised EVDS date format: {text!r}")


def parse_items(payload: dict[str, Any], code: str) -> list[Observation]:
    """Extracts (date, value) pairs from an EVDS response; skips empty values."""
    column = code.replace(".", "_")
    rows: list[Observation] = []
    for item in payload.get("items", []):
        value = item.get(column)
        if value in (None, ""):
            continue
        rows.append((parse_evds_date(item["Tarih"]), float(value)))
    return rows


def deduplicate(rows: list[Observation]) -> list[Observation]:
    """Keeps the last value per date and sorts by date."""
    return sorted(dict(rows).items())


def fetch_series(code: str, start: dt.date, end: dt.date, api_key: str) -> list[Observation]:
    """Fetches a series from EVDS3 in chunks (needs internet and an API key)."""
    rows: list[Observation] = []
    with httpx.Client(headers={"key": api_key}, timeout=30) as client:
        for window_start, window_end in date_windows(start, end):
            response = client.get(build_url(code, window_start, window_end))
            response.raise_for_status()
            rows.extend(parse_items(response.json(), code))
        return deduplicate(rows)


def save_series(session: Session, code: str, rows: list[Observation]) -> int:
    """Upserts observations by date. Returns the number of rows written."""
    for date, value in rows:
        session.merge(MacroObservation(code=code, date=date, value=value))
    session.commit()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch EVDS series into the database.")
    parser.add_argument("codes", nargs="+", help="Series codes, e.g. TP.DK.USD.A.YTL")
    parser.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2020, 1, 1))
    args = parser.parse_args()

    engine = get_engine()
    api_key = os.environ.get("EVDS_API_KEY")
    if not api_key:
        raise RuntimeError("EVDS_API_KEY is not set. Check the .env file.")

    init_db(engine)
    with Session(engine) as session:
        for code in args.codes:
            rows = fetch_series(code, args.start, dt.date.today(), api_key)
            count = save_series(session, code, rows)
            print(f"{code}: {count} observations saved")


if __name__ == "__main__":
    main()
