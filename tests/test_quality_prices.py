import datetime as dt

from bistlab.quality.prices import (
    Bar,
    assess,
    business_days_after,
    business_gaps,
    calendar_missing,
    find_jumps,
    is_bist,
    is_provisional,
    longest_flat_run,
    split_like,
    suspicious_jumps,
)

D = dt.date
UTC = dt.UTC


def bars(days: list[dt.date], close: float = 10.0) -> list[Bar]:
    fetched = dt.datetime.combine(days[-1] + dt.timedelta(days=1), dt.time(9), UTC)
    return [Bar(day, close + 0.01 * i, fetched) for i, day in enumerate(days)]


def test_provisional_when_fetched_same_local_day_or_missing() -> None:
    day = D(2026, 11, 25)
    assert is_provisional(Bar(day, 1.0, None))
    assert is_provisional(Bar(day, 1.0, dt.datetime(2026, 11, 25, 17, 0, tzinfo=UTC)))
    # 25 Kas 22:00 UTC = 26 Kas 01:00 İstanbul -> doğrulanmış
    assert not is_provisional(Bar(day, 1.0, dt.datetime(2026, 11, 25, 22, 0, tzinfo=UTC)))
    assert not is_provisional(Bar(day, 1.0, dt.datetime(2026, 11, 26, 18, 0)))


def test_find_jumps_skips_invalid_closes() -> None:
    series = [
        Bar(D(2026, 1, 1), 100.0, None),
        Bar(D(2026, 1, 2), None, None),
        Bar(D(2026, 1, 5), 110.0, None),
        Bar(D(2026, 1, 6), 55.0, None),
    ]
    assert find_jumps(series) == [(D(2026, 1, 6), -0.5)]


def test_calendar_missing_only_inside_series_range() -> None:
    calendar = [D(2026, 1, d) for d in (1, 2, 5, 6, 7, 8)]
    assert calendar_missing([D(2026, 1, 2), D(2026, 1, 7)], calendar) == [
        D(2026, 1, 5),
        D(2026, 1, 6),
    ]


def test_business_gaps_ignores_weekends_and_short_holidays() -> None:
    assert business_gaps([D(2026, 1, 9), D(2026, 1, 12)]) == []  # Cuma -> Pazartesi
    assert business_gaps([D(2026, 1, 5), D(2026, 1, 9)]) == []  # 3 iş günü boşluk
    gap = business_gaps([D(2026, 1, 5), D(2026, 1, 12)])
    assert gap == [D(2026, 1, d) for d in (6, 7, 8, 9)]


def test_business_days_after() -> None:
    assert business_days_after(D(2026, 1, 9), D(2026, 1, 12)) == 1
    assert business_days_after(D(2026, 1, 12), D(2026, 1, 9)) == 0


def test_is_bist_uses_suffix_and_calendar_share() -> None:
    calendar = {D(2026, 1, d) for d in range(1, 31)}
    assert is_bist("THYAO", [D(2026, 1, 2)], calendar)
    assert not is_bist("SAP.DE", [D(2026, 1, 2)], calendar)
    assert not is_bist("AAPL", [D(2026, 1, 2), D(2026, 2, 2)], calendar)


def test_assess_statuses() -> None:
    calendar = [D(2026, 1, d) for d in (5, 6, 7, 8, 9, 12, 13, 14, 15, 16)]
    good = assess("THYAO", bars(calendar), calendar)
    assert good.status == "İyi" and good.coverage == 1.0 and not good.provisional
    stale = assess("ASELS", bars(calendar[:5]), calendar)
    assert stale.stale == 5 and stale.status == "Sorunlu"
    # 10 günde 1 eksik = %90 kapsam -> sorunlu; uzun seride 1 eksik -> dikkat
    short_gap = assess("BIMAS", bars(calendar[:3] + calendar[4:]), calendar)
    assert short_gap.missing == [D(2026, 1, 8)] and short_gap.status == "Sorunlu"
    long_calendar = [D(2026, 1, 1) + dt.timedelta(days=i) for i in range(60)]
    long_gap = assess("EREGL", bars(long_calendar[:10] + long_calendar[11:]), long_calendar)
    assert len(long_gap.missing) == 1 and long_gap.status == "Dikkat"


def test_split_like_detects_split_ratios_only() -> None:
    assert split_like(4.0)  # ×5 (SOL.MC 2025-12-10)
    assert split_like(-0.5)  # ÷2
    assert split_like(-0.9)  # ÷10
    assert not split_like(-0.672)  # ÷3'e %1,6 uzak (MAXNQ gerçek düşüş)
    assert not split_like(0.30)


def closes(values: list[float]) -> list[Bar]:
    days = [D(2026, 1, d) for d in (5, 6, 7, 8, 9, 12)]
    return [Bar(day, close, None) for day, close in zip(days, values, strict=True)]


def test_suspicious_jumps_split_and_round_trip() -> None:
    assert suspicious_jumps(closes([10, 10, 50, 51, 52, 53])) == [
        (D(2026, 1, 7), 4.0, "bölünme oranı")
    ]
    found = suspicious_jumps(closes([10, 10, 17, 10.5, 10, 10]))
    assert [(day, reason) for day, _, reason in found] == [(D(2026, 1, 7), "geri dönen sıçrama")]
    assert suspicious_jumps(closes([10, 13, 9, 12, 8.5, 11])) == []


def test_longest_flat_run() -> None:
    assert longest_flat_run(closes([10, 11, 12, 13, 14, 15])) == 1
    assert longest_flat_run(closes([10, 10, 10, 11, 11, 12])) == 3
    assert longest_flat_run(closes([10, 10, 10, 10, 10, 10])) == 6


def test_foreign_series_one_business_day_behind_is_not_stale() -> None:
    calendar = [D(2026, 11, d) for d in (20, 23, 24, 25, 26)]
    us = bars([D(2026, 11, d) for d in (20, 23, 24, 25)])
    q = assess("ENR.DE", us, calendar)
    assert q.market == "Yabancı" and q.stale == 0 and q.status == "İyi"
    two_behind = assess("ENR.DE", bars([D(2026, 11, d) for d in (20, 23, 24)]), calendar)
    assert two_behind.stale == 1 and two_behind.status == "Dikkat"
