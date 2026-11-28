"""Data quality for price series: missing days, staleness, jumps, provisional last bar.

BIST series are checked against the XU100 trading calendar. Foreign series (overseas stocks
in the fund x-ray) follow other holiday calendars, so business-day gaps are checked instead:
more than 3 consecutive missing business days count as missing.

The last bar is "provisional" unless it was fetched on a later day (Istanbul time): Yahoo can
later withdraw or change that day's bar (the 25 Nov 2026 incident). Provisional status does
not affect the verdict; it is shown in its own column.

Jumps fall into two groups. "Suspicious" ones affect the status: the price ratio is within
±1.5% of a split or bonus-issue factor (×2, ×3, ×5, ×10 ... or the inverse), or after a jump
of at least 50% the price returns to its previous level within 3 trading days (a one-day bad
print). The rest are volatility and are only counted.

Flat price: the same close for FLAT_RUN consecutive trading days. Usually a trading halt or
the provider repeating the last price; it creates fake "zero volatility" in return and risk
calculations (SOL.MC: 1.598 throughout 2024–2025).
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import select

from bistlab.data.db import Price, Security, get_engine

LOCAL_TZ = ZoneInfo("Europe/Istanbul")
CALENDAR_TICKER = "XU100"
JUMP_THRESHOLD = 0.25
SPLIT_FACTORS = (2, 3, 4, 5, 10, 20, 25, 50, 100)
SPLIT_TOLERANCE = 0.015
SPIKE_MIN = 0.5
SPIKE_WINDOW = 3
SPIKE_RETURN = 0.10
FLAT_RUN = 10
FOREIGN_LAG = 1  # foreign exchanges: a 1-business-day lag is normal (time zones, holidays)
BIST_SHARE = 0.99
FOREIGN_GAP_BUSDAYS = 3
STALE_LIMIT = 3
MIN_COVERAGE = 0.95
STATUS_ORDER = {"Problem": 0, "Warning": 1, "Good": 2}


@dataclass(frozen=True)
class Bar:
    date: dt.date
    close: float | None
    fetched_at: dt.datetime | None


@dataclass(frozen=True)
class SeriesQuality:
    ticker: str
    market: str
    first: dt.date
    last: dt.date
    bars: int
    missing: list[dt.date]
    stale: int
    jumps: list[tuple[dt.date, float]]
    suspicious: list[tuple[dt.date, float, str]]
    flat_run: int
    bad_closes: int
    provisional: bool

    @property
    def coverage(self) -> float:
        expected = self.bars + len(self.missing)
        return self.bars / expected if expected else 0.0

    @property
    def status(self) -> str:
        if self.bad_closes or self.stale > STALE_LIMIT or self.coverage < MIN_COVERAGE:
            return "Problem"
        if self.suspicious or self.missing or self.stale or self.flat_run >= FLAT_RUN:
            return "Warning"
        return "Good"


def valid_close(close: float | None) -> bool:
    return close is not None and math.isfinite(close) and close > 0


def is_provisional(bar: Bar) -> bool:
    """A bar is provisional unless it was fetched on a day after its date."""
    if bar.fetched_at is None:
        return True
    fetched = bar.fetched_at
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=dt.UTC)
    return fetched.astimezone(LOCAL_TZ).date() <= bar.date


def valid_points(bars: list[Bar]) -> list[tuple[dt.date, float]]:
    return [
        (bar.date, bar.close)
        for bar in bars
        if bar.close is not None and math.isfinite(bar.close) and bar.close > 0
    ]


def find_jumps(bars: list[Bar], threshold: float = JUMP_THRESHOLD) -> list[tuple[dt.date, float]]:
    """Days whose absolute daily return exceeds the threshold."""
    points = valid_points(bars)
    jumps = []
    for (_, before), (day, close) in zip(points, points[1:], strict=False):
        change = close / before - 1
        if abs(change) > threshold:
            jumps.append((day, change))
    return jumps


def split_like(change: float, tolerance: float = SPLIT_TOLERANCE) -> bool:
    """Is the price ratio very close to a split or bonus-issue factor (or its inverse)?"""
    ratio = 1 + change
    return any(
        abs(ratio / factor - 1) < tolerance or abs(ratio * factor - 1) < tolerance
        for factor in SPLIT_FACTORS
    )


def suspicious_jumps(bars: list[Bar]) -> list[tuple[dt.date, float, str]]:
    """Jumps that suggest a data error: a split ratio, or a one-day move that reverts."""
    points = valid_points(bars)
    found = []
    for index in range(1, len(points)):
        before = points[index - 1][1]
        day, close = points[index]
        change = close / before - 1
        if abs(change) <= JUMP_THRESHOLD:
            continue
        if split_like(change):
            found.append((day, change, "split ratio"))
            continue
        after = points[index + 1 : index + 1 + SPIKE_WINDOW]
        if abs(change) >= SPIKE_MIN and any(
            abs(price / before - 1) <= SPIKE_RETURN for _, price in after
        ):
            found.append((day, change, "reverting jump"))
    return found


def longest_flat_run(bars: list[Bar]) -> int:
    """Longest run of identical consecutive closes (1 = no repeats)."""
    longest = current = 0
    previous: float | None = None
    for _, close in valid_points(bars):
        current = current + 1 if close == previous else 1
        longest = max(longest, current)
        previous = close
    return longest


def is_bist(ticker: str, dates: list[dt.date], calendar: set[dt.date]) -> bool:
    if "." in ticker or not dates:
        return False
    inside = sum(day in calendar for day in dates)
    return inside / len(dates) >= BIST_SHARE


def calendar_missing(dates: list[dt.date], calendar: list[dt.date]) -> list[dt.date]:
    present = set(dates)
    return [day for day in calendar if dates[0] <= day <= dates[-1] and day not in present]


def business_gaps(dates: list[dt.date]) -> list[dt.date]:
    """Days inside gaps longer than FOREIGN_GAP_BUSDAYS consecutive business days."""
    missing: list[dt.date] = []
    for previous, current in zip(dates, dates[1:], strict=False):
        start = np.datetime64(previous, "D") + np.timedelta64(1, "D")
        between = np.arange(start, np.datetime64(current, "D"), dtype="datetime64[D]")
        business = between[np.is_busday(between)]
        if len(business) > FOREIGN_GAP_BUSDAYS:
            missing.extend(business.tolist())
    return missing


def business_days_after(last: dt.date, reference: dt.date) -> int:
    if reference <= last:
        return 0
    one = dt.timedelta(days=1)
    return int(np.busday_count(last + one, reference + one))


def assess(ticker: str, bars: list[Bar], calendar: list[dt.date]) -> SeriesQuality:
    dates = [bar.date for bar in bars]
    calendar_set = set(calendar)
    bist = is_bist(ticker, dates, calendar_set)
    if bist:
        missing = calendar_missing(dates, calendar)
        stale = sum(day > dates[-1] for day in calendar)
    else:
        missing = business_gaps(dates)
        stale = max(0, business_days_after(dates[-1], calendar[-1]) - FOREIGN_LAG)
    return SeriesQuality(
        ticker=ticker,
        market="BIST" if bist else "Foreign",
        first=dates[0],
        last=dates[-1],
        bars=len(bars),
        missing=missing,
        stale=stale,
        jumps=find_jumps(bars),
        suspicious=suspicious_jumps(bars),
        flat_run=longest_flat_run(bars),
        bad_closes=sum(not valid_close(bar.close) for bar in bars),
        provisional=is_provisional(bars[-1]),
    )


def assess_all(series: dict[str, list[Bar]]) -> list[SeriesQuality]:
    if CALENDAR_TICKER not in series:
        raise SystemExit(f"No {CALENDAR_TICKER} series; cannot build the trading calendar.")
    calendar = [bar.date for bar in series[CALENDAR_TICKER] if valid_close(bar.close)]
    results = [assess(ticker, bars, calendar) for ticker, bars in series.items() if bars]
    return sorted(results, key=lambda q: (STATUS_ORDER[q.status], q.ticker))


def load_bars() -> dict[str, list[Bar]]:
    stmt = (
        select(Security.ticker, Price.date, Price.close, Price.fetched_at)
        .join(Security, Security.id == Price.security_id)
        .order_by(Security.ticker, Price.date)
    )
    series: dict[str, list[Bar]] = {}
    with get_engine().connect() as conn:
        for ticker, date, close, fetched_at in conn.execute(stmt):
            series.setdefault(ticker, []).append(Bar(date, close, fetched_at))
    return series


def render(results: list[SeriesQuality], only_issues: bool = False) -> str:
    header = (
        f"{'Ticker':<10}{'Market':<9}{'First':<12}{'Last':<12}{'Bars':>6}{'Coverage':>9}"
        f"{'Missing':>8}{'Stale':>7}{'Jumps':>7}{'Suspect':>9}{'Flat':>6}{'Prov.':>7}  Status"
    )
    lines = [header]
    for q in results:
        if only_issues and q.status == "Good":
            continue
        lines.append(
            f"{q.ticker:<10}{q.market:<9}{q.first.isoformat():<12}{q.last.isoformat():<12}"
            f"{q.bars:>6}{q.coverage:>9.1%}{len(q.missing):>8}{q.stale:>7}"
            f"{len(q.jumps):>7}{len(q.suspicious):>9}{q.flat_run:>6}"
            f"{'yes' if q.provisional else '':>7}  {q.status}"
        )
    counts = {status: sum(q.status == status for q in results) for status in STATUS_ORDER}
    provisional = sum(q.provisional for q in results)
    lines.append("")
    lines.append(
        f"{len(results)} series: {counts['Good']} good, {counts['Warning']} warning, "
        f"{counts['Problem']} problem; last bar provisional in {provisional} series."
    )
    lines.append(
        f"Calendar: {CALENDAR_TICKER}. Jump: daily ±{JUMP_THRESHOLD:.0%}; suspicious: split "
        "ratio or a ≥50% jump that reverts within 3 days. "
        f"Flat: longest run of identical closes (≥ {FLAT_RUN} = warning). "
        f"Problem: stale > {STALE_LIMIT} days, coverage < {MIN_COVERAGE:.0%} "
        "or an invalid close."
    )
    return "\n".join(lines)


def render_detail(q: SeriesQuality) -> str:
    lines = [f"{q.ticker} ({q.market}) — {q.status}"]
    lines.append(
        f"  Missing days ({len(q.missing)}): "
        + ", ".join(day.isoformat() for day in q.missing[:20])
        + (" …" if len(q.missing) > 20 else "")
    )
    for day, change, reason in q.suspicious:
        lines.append(f"  Suspicious {day.isoformat()}: {change:+.1%} ({reason})")
    lines.append(f"  Longest flat-price run: {q.flat_run} trading days")
    others = len(q.jumps) - len(q.suspicious)
    lines.append(f"  Other jumps (volatility, above ±{JUMP_THRESHOLD:.0%}): {others}")
    state = "provisional" if q.provisional else "confirmed"
    lines.append(f"  Last bar {q.last.isoformat()}: {state}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Price-series data quality report")
    parser.add_argument("--issues", action="store_true", help="show only series that are not Good")
    parser.add_argument("--detail", nargs="*", default=[], help="tickers to show in detail")
    args = parser.parse_args()
    results = assess_all(load_bars())
    print(render(results, only_issues=args.issues))
    wanted = {code.upper() for code in args.detail}
    for q in results:
        if q.ticker.upper() in wanted:
            print()
            print(render_detail(q))


if __name__ == "__main__":
    main()
