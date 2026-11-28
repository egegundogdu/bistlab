"""Macro stress test: impact of FX and market shocks on stocks and a portfolio.

Each stock's weekly TRY return is explained by two factors (last `--years` years):

    r_stock = a + b_market · r_XU100 + b_fx · r_USDTRY + e

Hypothetical scenario: estimated impact = b_market · shock_market + b_fx · shock_fx.
Historical scenario: find XU100's worst `--window` trading days in the data and compare
the stocks' actual returns over those days with the model's estimate for the same
factor moves. A linear model can break in large shocks; the comparison shows how much
tail risk it misses.

Read the FX beta with care: weekly USD/TRY moves are small and steady (a managed path),
so the coefficient is noisy. An FX beta with |t| < 2 is set to 0 in the scenarios; the
scenario FX shock is far outside the largest weekly move in the data, and the report
says so (in the first run, meaningless betas such as ASELS +2.65 and BIMAS −2.12
turned a 20% shock into −81% / +59% impacts).
"""

from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pandas as pd

from bistlab.data.db import get_engine
from bistlab.real.view import (
    DEFAULT_TICKERS,
    FX_CODES,
    MARKET,
    Points,
    load_macro,
    load_prices,
    value_asof,
)

Array = npt.NDArray[np.float64]

T_LIMIT = 2.0

SCENARIOS: list[tuple[str, float, float]] = [
    ("FX shock (XU100 −10%, USD/TRY +20%)", -0.10, 0.20),
    ("Market crash (XU100 −25%, USD/TRY +5%)", -0.25, 0.05),
    ("Combined (XU100 −20%, USD/TRY +30%)", -0.20, 0.30),
]


@dataclass(frozen=True)
class Betas:
    alpha: float
    market: float
    fx: float
    r2: float
    n: int
    se_market: float
    se_fx: float

    @property
    def t_fx(self) -> float:
        return self.fx / self.se_fx if self.se_fx > 0 else 0.0

    @property
    def fx_used(self) -> float:
        """FX beta used in scenarios: 0 when not significant (|t| < T_LIMIT)."""
        return self.fx if abs(self.t_fx) >= T_LIMIT else 0.0


def factor_betas(y: Array, market: Array, fx: Array) -> Betas:
    """Least squares: y = a + b_m · market + b_fx · fx."""
    design = np.column_stack([np.ones_like(market), market, fx])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    residual = y - design @ coef
    ssr = float(np.sum(residual**2))
    total = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ssr / total if total > 0 else 0.0
    dof = max(len(y) - 3, 1)
    covariance = ssr / dof * np.linalg.pinv(design.T @ design)
    se = np.sqrt(np.clip(np.diag(covariance), 0.0, None))
    return Betas(
        float(coef[0]), float(coef[1]), float(coef[2]), r2, len(y), float(se[1]), float(se[2])
    )


def scenario_impact(betas: Betas, market_shock: float, fx_shock: float) -> float:
    """Estimated impact; an insignificant FX beta counts as 0."""
    return betas.market * market_shock + betas.fx_used * fx_shock


def worst_window(closes: pd.Series[float], days: int) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    """Worst return over `days` trading days: (start close, end close, return)."""
    change = closes / closes.shift(days) - 1
    position = int(np.nanargmin(change.to_numpy(dtype=float)))
    start, end = closes.index[position - days], closes.index[position]
    return start, end, float(change.iloc[position])


def window_return(points: Points, start: dt.date, end: dt.date) -> float | None:
    first, last = value_asof(points, start), value_asof(points, end)
    if first is None or last is None:
        return None
    return last / first - 1


def to_series(points: Points) -> pd.Series[float]:
    index = pd.DatetimeIndex([pd.Timestamp(day) for day, _ in points])
    return pd.Series([value for _, value in points], index=index, dtype=float)


def weekly_returns(points: Points) -> pd.Series[float]:
    return to_series(points).resample("W-FRI").last().pct_change().dropna()


def max_weekly_move(points: Points) -> float:
    """Largest absolute weekly change in the data."""
    weekly = weekly_returns(points)
    return float(weekly.abs().max()) if len(weekly) else 0.0


def fit_all(prices: dict[str, Points], market: Points, usd: Points) -> dict[str, Betas]:
    frame = pd.DataFrame({"market": weekly_returns(market), "fx": weekly_returns(usd)}).dropna()
    betas = {}
    for ticker, points in prices.items():
        data = frame.join(weekly_returns(points).rename("y"), how="inner").dropna()
        if len(data) < 26:
            continue
        betas[ticker] = factor_betas(
            np.asarray(data["y"], dtype=np.float64),
            np.asarray(data["market"], dtype=np.float64),
            np.asarray(data["fx"], dtype=np.float64),
        )
    return betas


def render(
    betas: dict[str, Betas],
    history: tuple[dt.date, dt.date, float, float],
    actual: dict[str, float],
    max_fx: float,
    in_sample: bool = False,
) -> str:
    lines = ["Factor betas (weekly TRY returns; XU100 and USD/TRY)"]
    lines.append(
        f"{'Ticker':<8}{'b_market':>10}{'b_fx':>9}{'t_fx':>8}{'In scen.':>11}{'R²':>7}{'Weeks':>7}"
    )
    for ticker, b in betas.items():
        lines.append(
            f"{ticker:<8}{b.market:>10.2f}{b.fx:>9.2f}{b.t_fx:>8.1f}{b.fx_used:>11.2f}"
            f"{b.r2:>7.2f}{b.n:>7}"
        )
    lines.append(f'FX beta with |t| < {T_LIMIT:.0f} is set to 0 in scenarios ("In scen." column).')

    lines += ["", "Hypothetical scenarios — estimated instant impact (TRY)"]
    header = f"{'Ticker':<10}" + "".join(f"{f'S{i + 1}':>9}" for i in range(len(SCENARIOS)))
    lines.append(header)
    impacts = {t: [scenario_impact(b, m, f) for _, m, f in SCENARIOS] for t, b in betas.items()}
    for ticker, row in impacts.items():
        lines.append(f"{ticker:<10}" + "".join(f"{v:>9.1%}" for v in row))
    if impacts:
        portfolio = np.mean(list(impacts.values()), axis=0)
        lines.append(f"{'Portfolio':<10}" + "".join(f"{v:>9.1%}" for v in portfolio))
    for i, (name, _, _) in enumerate(SCENARIOS):
        lines.append(f"  S{i + 1}: {name}")
    lines.append("  Portfolio: equal weight (mean of the estimated impacts).")
    biggest = max(abs(f) for _, _, f in SCENARIOS)
    if biggest > max_fx:
        lines.append(
            f"  Warning: the largest weekly USD/TRY move in the data is {max_fx * 100:.1f}%; "
            f"a {biggest * 100:.0f}% FX shock is out of sample, so the linear estimate is weak."
        )

    start, end, market_move, fx_move = history
    lines += [
        "",
        f"Historical scenario: worst XU100 window {start} → {end}: "
        f"XU100 {market_move:+.1%}, USD/TRY {fx_move:+.1%}",
        f"{'Ticker':<8}{'Actual':>9}{'Model':>9}{'Diff.':>9}",
    ]
    if in_sample:
        lines.insert(
            -1,
            "Note: the window is inside the beta estimation period — an in-sample test, "
            "not a true out-of-sample check.",
        )
    errors = []
    for ticker, b in betas.items():
        if ticker not in actual:
            continue
        model = scenario_impact(b, market_move, fx_move)
        errors.append(actual[ticker] - model)
        lines.append(
            f"{ticker:<8}{actual[ticker]:>9.1%}{model:>9.1%}{actual[ticker] - model:>+9.1%}"
        )
    if errors:
        lines.append(
            f"Mean difference {np.mean(errors):+.1%}, mean absolute difference "
            f"{np.mean(np.abs(errors)):.1%} (negative = the model understated the loss)."
        )
    lines.append("\nFor education; not investment advice.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Macro stress test (FX and market shocks)")
    parser.add_argument("tickers", nargs="*", default=DEFAULT_TICKERS)
    parser.add_argument("--years", type=float, default=2.0, help="beta estimation window (years)")
    parser.add_argument("--window", type=int, default=5, help="historical window (trading days)")
    args = parser.parse_args()
    since = dt.date.today() - dt.timedelta(days=round(365.25 * args.years))
    with get_engine().connect() as conn:
        usd = load_macro(conn, FX_CODES["USD"])
        market = load_prices(conn, MARKET, dt.date(2000, 1, 1))
        prices_all = {t: load_prices(conn, t, dt.date(2000, 1, 1)) for t in args.tickers}
    if not usd or not market:
        raise SystemExit("No USD/TRY or XU100 data.")
    recent = {t: [p for p in pts if p[0] >= since] for t, pts in prices_all.items()}
    betas = fit_all(
        recent,
        [p for p in market if p[0] >= since],
        [p for p in usd if p[0] >= since],
    )
    market_series = to_series(market)
    start_ts, end_ts, market_move = worst_window(market_series, args.window)
    start, end = start_ts.date(), end_ts.date()
    fx_move = window_return(usd, start, end) or 0.0
    actual = {
        t: r for t, pts in prices_all.items() if (r := window_return(pts, start, end)) is not None
    }
    recent_usd = [p for p in usd if p[0] >= since]
    print(
        render(
            betas,
            (start, end, market_move, fx_move),
            actual,
            max_weekly_move(recent_usd),
            start >= since,
        )
    )


if __name__ == "__main__":
    main()
