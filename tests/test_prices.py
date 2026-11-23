import datetime as dt

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bistlab.data.db import Price, get_engine, init_db
from bistlab.data.prices import normalize_prices, save_prices, to_yahoo_symbol


def _raw_sample() -> pd.DataFrame:
    index = pd.DatetimeIndex(["2026-01-02", "2026-01-05"], tz="Europe/Istanbul")
    return pd.DataFrame(
        {
            "Open": [10.0, 10.5],
            "High": [11.0, 11.2],
            "Low": [9.8, 10.1],
            "Close": [10.6, 11.0],
            "Volume": [1000, 1500],
            "Dividends": [0.0, 0.0],
        },
        index=index,
    )


def test_to_yahoo_symbol() -> None:
    assert to_yahoo_symbol("thyao") == "THYAO.IS"
    assert to_yahoo_symbol("ASELS.IS") == "ASELS.IS"


def test_normalize_prices() -> None:
    df = normalize_prices(_raw_sample())
    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert df.loc[0, "date"] == dt.date(2026, 1, 2)
    assert df.loc[1, "close"] == 11.0


def test_save_prices_twice_does_not_duplicate() -> None:
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    prices = normalize_prices(_raw_sample())
    with Session(engine) as session:
        save_prices(session, "TEST", prices)
        save_prices(session, "TEST", prices)
        count = session.scalar(select(func.count()).select_from(Price))
    assert count == 2
