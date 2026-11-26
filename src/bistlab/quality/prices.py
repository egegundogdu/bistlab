"""Fiyat serileri için veri kalitesi: eksik gün, bayatlık, sıçrama, geçici son gün.

BIST serileri XU100'ün işlem takvimine göre denetlenir. Yabancı borsa serileri (fon
röntgenindeki yurt dışı hisseler) farklı tatil takvimine sahip olduğu için iş günü
boşluklarına bakılır: art arda 3'ten fazla iş günü yoksa eksik sayılır.

Son çubuk, tarihinden sonraki bir günde (İstanbul saatiyle) çekilmediyse "geçici"dir:
Yahoo o günün çubuğunu sonradan geri çekebilir ya da değiştirebilir (25 Kas 2026 olayı).
Geçicilik durumu bozmaz; ayrı sütunda gösterilir.

Sıçramalar ikiye ayrılır. "Şüpheli" olanlar durumu etkiler: oran bir bölünme / bedelsiz
katsayısına (×2, ×3, ×5, ×10 ... ya da tersi) ±%1,5 yakınsa ya da en az %50'lik bir
sıçramadan sonra fiyat 3 işlem günü içinde eski seviyesine dönüyorsa (tek günlük hatalı
fiyat). Diğerleri oynaklıktır; sadece sayılır.

Donuk fiyat: art arda FLAT_RUN işlem günü aynı kapanış. Genelde işlem durdurma ya da
sağlayıcının son fiyatı tekrar yazmasıdır; getiri ve risk hesaplarında sahte "sıfır
oynaklık" yaratır (SOL.MC: 2024–2025 boyunca 1,598).
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
BIST_SHARE = 0.99
FOREIGN_GAP_BUSDAYS = 3
STALE_LIMIT = 3
MIN_COVERAGE = 0.95
STATUS_ORDER = {"Sorunlu": 0, "Dikkat": 1, "İyi": 2}


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
            return "Sorunlu"
        if self.suspicious or self.missing or self.stale or self.flat_run >= FLAT_RUN:
            return "Dikkat"
        return "İyi"


def valid_close(close: float | None) -> bool:
    return close is not None and math.isfinite(close) and close > 0


def is_provisional(bar: Bar) -> bool:
    """Çubuk, tarihinden sonraki bir günde çekilmemişse geçicidir."""
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
    """Mutlak günlük getirisi eşiği aşan günler."""
    points = valid_points(bars)
    jumps = []
    for (_, before), (day, close) in zip(points, points[1:], strict=False):
        change = close / before - 1
        if abs(change) > threshold:
            jumps.append((day, change))
    return jumps


def split_like(change: float, tolerance: float = SPLIT_TOLERANCE) -> bool:
    """Fiyat oranı bir bölünme / bedelsiz katsayısına ya da tersine çok yakın mı."""
    ratio = 1 + change
    return any(
        abs(ratio / factor - 1) < tolerance or abs(ratio * factor - 1) < tolerance
        for factor in SPLIT_FACTORS
    )


def suspicious_jumps(bars: list[Bar]) -> list[tuple[dt.date, float, str]]:
    """Veri hatası şüphesi taşıyan sıçramalar: bölünme oranı ya da geri dönen tek gün."""
    points = valid_points(bars)
    found = []
    for index in range(1, len(points)):
        before = points[index - 1][1]
        day, close = points[index]
        change = close / before - 1
        if abs(change) <= JUMP_THRESHOLD:
            continue
        if split_like(change):
            found.append((day, change, "bölünme oranı"))
            continue
        after = points[index + 1 : index + 1 + SPIKE_WINDOW]
        if abs(change) >= SPIKE_MIN and any(
            abs(price / before - 1) <= SPIKE_RETURN for _, price in after
        ):
            found.append((day, change, "geri dönen sıçrama"))
    return found


def longest_flat_run(bars: list[Bar]) -> int:
    """Art arda aynı kapanışın en uzun tekrar sayısı (1 = hiç tekrar yok)."""
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
    """Art arda FOREIGN_GAP_BUSDAYS'ten fazla iş günü boşluğu olan yerlerdeki günler."""
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
        stale = business_days_after(dates[-1], calendar[-1])
    return SeriesQuality(
        ticker=ticker,
        market="BIST" if bist else "Yabancı",
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
        raise SystemExit(f"{CALENDAR_TICKER} serisi yok; takvim kurulamıyor.")
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
        f"{'Kod':<10}{'Piyasa':<9}{'İlk':<12}{'Son':<12}{'Gün':>6}{'Kapsam':>9}"
        f"{'Eksik':>7}{'Bayat':>7}{'Sıçrama':>9}{'Şüpheli':>9}{'Donuk':>7}{'Geçici':>8}  Durum"
    )
    lines = [header]
    for q in results:
        if only_issues and q.status == "İyi":
            continue
        lines.append(
            f"{q.ticker:<10}{q.market:<9}{q.first.isoformat():<12}{q.last.isoformat():<12}"
            f"{q.bars:>6}{q.coverage:>9.1%}{len(q.missing):>7}{q.stale:>7}"
            f"{len(q.jumps):>9}{len(q.suspicious):>9}{q.flat_run:>7}"
            f"{'evet' if q.provisional else '':>8}  {q.status}"
        )
    counts = {status: sum(q.status == status for q in results) for status in STATUS_ORDER}
    provisional = sum(q.provisional for q in results)
    lines.append("")
    lines.append(
        f"{len(results)} seri: {counts['İyi']} iyi, {counts['Dikkat']} dikkat, "
        f"{counts['Sorunlu']} sorunlu; {provisional} seride son gün geçici."
    )
    lines.append(
        f"Takvim: {CALENDAR_TICKER}. Sıçrama: günlük ±{JUMP_THRESHOLD:.0%}; şüpheli: bölünme "
        "oranı ya da 3 günde geri dönen ≥%50 sıçrama. "
        f"Donuk: en uzun aynı kapanış serisi (≥ {FLAT_RUN} dikkat). "
        f"Sorunlu: bayat > {STALE_LIMIT} gün, kapsam < {MIN_COVERAGE:.0%} "
        "ya da geçersiz kapanış."
    )
    return "\n".join(lines)


def render_detail(q: SeriesQuality) -> str:
    lines = [f"{q.ticker} ({q.market}) — {q.status}"]
    lines.append(
        f"  Eksik günler ({len(q.missing)}): "
        + ", ".join(day.isoformat() for day in q.missing[:20])
        + (" …" if len(q.missing) > 20 else "")
    )
    for day, change, reason in q.suspicious:
        lines.append(f"  Şüpheli {day.isoformat()}: {change:+.1%} ({reason})")
    lines.append(f"  En uzun donuk fiyat serisi: {q.flat_run} işlem günü")
    others = len(q.jumps) - len(q.suspicious)
    lines.append(f"  Diğer sıçramalar (oynaklık, ±{JUMP_THRESHOLD:.0%} üstü): {others}")
    state = "geçici" if q.provisional else "doğrulanmış"
    lines.append(f"  Son çubuk {q.last.isoformat()}: {state}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fiyat serisi veri kalitesi raporu")
    parser.add_argument("--issues", action="store_true", help="sadece iyi olmayanları göster")
    parser.add_argument("--detail", nargs="*", default=[], help="ayrıntısı gösterilecek kodlar")
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
