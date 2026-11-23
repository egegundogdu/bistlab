import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bistlab.data.db import MacroObservation, get_engine, init_db
from bistlab.data.evds import build_url, parse_evds_date, parse_items, save_series

SAMPLE = {
    "totalCount": 3,
    "items": [
        {"Tarih": "2026-1", "TP_DK_USD_A_YTL": "43.11246667", "UNIXTIME": {}},
        {"Tarih": "2026-2", "TP_DK_USD_A_YTL": "43.58569500", "UNIXTIME": {}},
        {"Tarih": "2026-3", "TP_DK_USD_A_YTL": None, "UNIXTIME": {}},
    ],
}


def test_build_url_puts_dates_in_evds_format() -> None:
    url = build_url("TP.DK.USD.A.YTL", dt.date(2026, 1, 1), dt.date(2026, 11, 20))
    assert url.endswith("series=TP.DK.USD.A.YTL&startDate=01-01-2026&endDate=20-11-2026&type=json")


def test_parse_evds_date() -> None:
    assert parse_evds_date("15-01-2026") == dt.date(2026, 1, 15)
    assert parse_evds_date("2026-3") == dt.date(2026, 3, 1)


def test_parse_items_skips_missing_values() -> None:
    rows = parse_items(SAMPLE, "TP.DK.USD.A.YTL")
    assert rows == [(dt.date(2026, 1, 1), 43.11246667), (dt.date(2026, 2, 1), 43.585695)]


def test_save_series_twice_does_not_duplicate() -> None:
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    rows = parse_items(SAMPLE, "TP.DK.USD.A.YTL")
    with Session(engine) as session:
        save_series(session, "TP.DK.USD.A.YTL", rows)
        save_series(session, "TP.DK.USD.A.YTL", rows)
        count = session.scalar(select(func.count()).select_from(MacroObservation))
    assert count == 2


def test_date_windows_cover_range_without_gaps_or_overlap() -> None:
    from bistlab.data.evds import date_windows

    windows = date_windows(dt.date(2023, 1, 1), dt.date(2025, 6, 30), max_days=365)
    assert windows[0][0] == dt.date(2023, 1, 1)
    assert windows[-1][1] == dt.date(2025, 6, 30)
    for (_, prev_end), (next_start, _) in zip(windows, windows[1:], strict=False):
        assert next_start == prev_end + dt.timedelta(days=1)
    assert all((end - start).days < 365 for start, end in windows)


def test_deduplicate_keeps_one_row_per_date() -> None:
    from bistlab.data.evds import deduplicate

    rows = [
        (dt.date(2008, 12, 1), 1.0),
        (dt.date(2009, 1, 1), 2.0),
        (dt.date(2008, 12, 1), 1.0),
    ]
    assert deduplicate(rows) == [(dt.date(2008, 12, 1), 1.0), (dt.date(2009, 1, 1), 2.0)]
