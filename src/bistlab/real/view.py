"""Reel TL ve USD görünümü; TMS 29 FCF'sini bugünkü satın alma gücüne taşıma.

Nominal TL getirisi yüksek enflasyonda yanıltıcıdır. Fiyat serileri TÜFE
(TP.TUKFIY2025.GENEL, aylık, 2025=100) ile reel TL'ye, TCMB döviz alış kuru
(TP.DK.USD.A.YTL, günlük) ile USD'ye çevrilir. Bir günün TÜFE'si o ayın endeksidir;
ay henüz yayımlanmadıysa son yayımlanan ay kullanılır ve raporda belirtilir.

TMS 29 uygulayan şirketler yıl sonu tablolarını o tarihin satın alma gücüyle verir;
piyasa değeri ise bugünün fiyatıdır. Karşılaştırma için FCF bugüne taşınır:
FCF × TÜFE(son ay) / TÜFE(dönem sonu ayı). Yabancı para raporlayanlarda (THYAO: USD)
TÜFE düzeltmesi yapılmaz; piyasa değeri raporlama para birimine çevrilir.
"""

from __future__ import annotations

import argparse
import bisect
import datetime as dt
import math
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from bistlab.data.db import get_engine

CPI_CODE = "TP.TUKFIY2025.GENEL"
FX_CODES = {"USD": "TP.DK.USD.A.YTL", "EUR": "TP.DK.EUR.A.YTL"}
MARKET = "XU100"
DEFAULT_TICKERS = ["THYAO", "ASELS", "PGSUS", "FROTO", "TUPRS", "BIMAS", "EREGL", "TCELL"]

Points = list[tuple[dt.date, float]]


def month_start(day: dt.date) -> dt.date:
    return day.replace(day=1)


def cpi_for(cpi: dict[dt.date, float], day: dt.date) -> tuple[float, bool]:
    """Günün ayına ait TÜFE. Ay yayımlanmadıysa son ay; ikinci değer bunu bildirir."""
    key = month_start(day)
    if key in cpi:
        return cpi[key], False
    latest = max(cpi)
    if key > latest:
        return cpi[latest], True
    raise KeyError(f"{key.isoformat()}: no CPI data")


def value_asof(points: Points, day: dt.date) -> float | None:
    """Verilen gün ya da öncesindeki son değer."""
    index = bisect.bisect_right([d for d, _ in points], day) - 1
    return points[index][1] if index >= 0 else None


def annualize(total: float, years: float) -> float:
    return (1 + total) ** (1 / years) - 1 if years > 0 else math.nan


@dataclass(frozen=True)
class Performance:
    ticker: str
    start: dt.date
    end: dt.date
    nominal: float
    real: float
    usd: float
    cpi_estimated: bool

    @property
    def years(self) -> float:
        return (self.end - self.start).days / 365.25


def performance(ticker: str, prices: Points, cpi: dict[dt.date, float], usd: Points) -> Performance:
    (start, first), (end, last) = prices[0], prices[-1]
    nominal = last / first - 1
    cpi_start, _ = cpi_for(cpi, start)
    cpi_end, estimated = cpi_for(cpi, end)
    usd_start, usd_end = value_asof(usd, start), value_asof(usd, end)
    if usd_start is None or usd_end is None:
        raise ValueError(f"{ticker}: {start}: no USD/TRY data")
    return Performance(
        ticker=ticker,
        start=start,
        end=end,
        nominal=nominal,
        real=(1 + nominal) * cpi_start / cpi_end - 1,
        usd=(last / usd_end) / (first / usd_start) - 1,
        cpi_estimated=estimated,
    )


def restatement_factor(period_end: dt.date, cpi: dict[dt.date, float]) -> float:
    """Dönem sonu satın alma gücünden son yayımlanan aya taşıma katsayısı."""
    period_cpi, _ = cpi_for(cpi, period_end)
    return cpi[max(cpi)] / period_cpi


@dataclass(frozen=True)
class FcfYield:
    ticker: str
    currency: str
    period_end: dt.date
    fcf: float
    market_cap: float
    factor: float

    @property
    def nominal_yield(self) -> float:
        return self.fcf / self.market_cap

    @property
    def restated_yield(self) -> float:
        return self.fcf * self.factor / self.market_cap


def fcf_yield(
    ticker: str,
    currency: str,
    period_end: dt.date,
    fcf: float,
    shares: float,
    price_try: float,
    fx_try: float,
    cpi: dict[dt.date, float],
) -> FcfYield:
    """FCF getirisi; piyasa değeri raporlama para biriminde."""
    if currency == "TRY":
        market_cap, factor = price_try * shares, restatement_factor(period_end, cpi)
    else:
        market_cap, factor = price_try * shares / fx_try, 1.0
    return FcfYield(ticker, currency, period_end, fcf, market_cap, factor)


def load_points(conn: Connection, sql: str, **params: object) -> Points:
    return [(row[0], float(row[1])) for row in conn.execute(text(sql), params)]


def load_macro(conn: Connection, code: str) -> Points:
    return load_points(
        conn, "SELECT date, value FROM macro_observations WHERE code = :c ORDER BY date", c=code
    )


def load_prices(conn: Connection, ticker: str, since: dt.date) -> Points:
    return load_points(
        conn,
        "SELECT p.date, p.close FROM prices p JOIN securities s ON s.id = p.security_id "
        "WHERE s.ticker = :t AND p.date >= :d AND p.close > 0 ORDER BY p.date",
        t=ticker,
        d=since,
    )


def latest_fcf_inputs(conn: Connection, ticker: str) -> tuple[dt.date, str, float, float] | None:
    """Son dönemin (dönem sonu, para birimi, FCF, hisse sayısı)."""
    rows = conn.execute(
        text(
            "SELECT f.period_end, f.item, f.value, f.currency FROM financial_items f "
            "JOIN securities s ON s.id = f.security_id WHERE s.ticker = :t "
            "AND f.item IN ('Free Cash Flow', 'Ordinary Shares Number') "
            "AND f.value IS NOT NULL ORDER BY f.period_end DESC"
        ),
        {"t": ticker},
    ).all()
    fcf = next((row for row in rows if row[1] == "Free Cash Flow"), None)
    shares = next((row for row in rows if row[1] == "Ordinary Shares Number"), None)
    if fcf is None or shares is None:
        return None
    return fcf[0], str(fcf[3]), float(fcf[2]), float(shares[2])


def render_returns(results: list[Performance], cpi_change: float, usd_change: float) -> str:
    first = results[0]
    lines = [
        f"Getiri: {first.start} → {first.end} ({first.years:.1f} yıl). "
        f"Dönemde TÜFE {cpi_change:+.0%}, USD/TRY {usd_change:+.0%}.",
        "",
        f"{'':8}{'Toplam getiri':^33}{'Yıllık getiri':^33}",
        f"{'Kod':<8}{'Nominal TL':>11}{'Reel TL':>11}{'USD':>11}"
        f"{'Nominal TL':>11}{'Reel TL':>11}{'USD':>11}",
    ]
    for p in results:
        lines.append(
            f"{p.ticker:<8}{p.nominal:>11.0%}{p.real:>11.0%}{p.usd:>11.0%}"
            f"{annualize(p.nominal, p.years):>11.1%}{annualize(p.real, p.years):>11.1%}"
            f"{annualize(p.usd, p.years):>11.1%}"
        )
    if any(p.cpi_estimated for p in results):
        lines.append("Not: son ayın TÜFE'si henüz yayımlanmadı; son yayımlanan ay kullanıldı.")
    return "\n".join(lines)


def render_fcf(results: list[FcfYield], latest_cpi_month: dt.date) -> str:
    lines = [
        f"FCF getirisi: yıl sonu TMS 29 FCF'si → {latest_cpi_month:%Y-%m} satın alma gücü",
        f"{'Kod':<8}{'PB':<5}{'Dönem':<12}{'FCF (mr)':>10}{'PD (mr)':>10}"
        f"{'FCF/PD':>9}{'Katsayı':>9}{'Bugünkü':>9}",
    ]
    for r in results:
        lines.append(
            f"{r.ticker:<8}{r.currency:<5}{r.period_end.isoformat():<12}{r.fcf / 1e9:>10.1f}"
            f"{r.market_cap / 1e9:>10.1f}{r.nominal_yield:>9.1%}{r.factor:>9.2f}"
            f"{r.restated_yield:>9.1%}"
        )
    lines.append(
        "Katsayı > 1: yıl sonu lirası bugünün lirasından değerli; FCF bugüne taşınınca getiri "
        "artar. USD raporlayanlarda katsayı 1."
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reel TL / USD getiri ve TÜFE uyumlu FCF")
    parser.add_argument("tickers", nargs="*", default=DEFAULT_TICKERS)
    parser.add_argument("--since", type=dt.date.fromisoformat, default=dt.date(2023, 1, 2))
    args = parser.parse_args()
    with get_engine().connect() as conn:
        cpi = dict(load_macro(conn, CPI_CODE))
        usd = load_macro(conn, FX_CODES["USD"])
        if not cpi or not usd:
            raise SystemExit("No CPI or USD/TRY series; fetch the macro data first.")
        results = []
        for ticker in [MARKET, *args.tickers]:
            prices = load_prices(conn, ticker, args.since)
            if len(prices) < 2:
                print(f"{ticker}: fiyat yok, atlandı")
                continue
            results.append(performance(ticker, prices, cpi, usd))
        if results:
            start, end = results[0].start, results[0].end
            cpi_change = cpi_for(cpi, end)[0] / cpi_for(cpi, start)[0] - 1
            usd_end, usd_start = value_asof(usd, end), value_asof(usd, start)
            usd_change = (usd_end or math.nan) / (usd_start or math.nan) - 1
            print(render_returns(results, cpi_change, usd_change))
        print()
        yields = []
        for ticker in args.tickers:
            inputs = latest_fcf_inputs(conn, ticker)
            prices = load_prices(conn, ticker, args.since)
            if inputs is None or not prices:
                print(f"{ticker}: FCF ya da hisse sayısı yok, atlandı")
                continue
            period_end, currency, fcf, shares = inputs
            fx = 1.0
            if currency != "TRY":
                if currency not in FX_CODES:
                    print(f"{ticker}: {currency} kuru yok, atlandı")
                    continue
                fx = value_asof(load_macro(conn, FX_CODES[currency]), prices[-1][0]) or math.nan
            yields.append(
                fcf_yield(ticker, currency, period_end, fcf, shares, prices[-1][1], fx, cpi)
            )
        print(render_fcf(yields, max(cpi)))
    print("\nEğitim amaçlıdır; yatırım tavsiyesi değildir.")


if __name__ == "__main__":
    main()
