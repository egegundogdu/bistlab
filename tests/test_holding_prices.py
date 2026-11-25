import datetime as dt

import pandas as pd

from bistlab.funds.holding_prices import normalize_history, storage_ticker, to_yahoo


def test_to_yahoo_maps_exchanges() -> None:
    assert to_yahoo("SAHOL", "equity_tr") == "SAHOL.IS"
    assert to_yahoo("ENR GY", "equity_foreign") == "ENR.DE"
    assert to_yahoo("FORTUM FH", "equity_foreign") == "FORTUM.HE"
    assert to_yahoo("NEE US", "equity_foreign") == "NEE"
    assert to_yahoo("1407 JT", "equity_foreign") == "1407.T"


def test_to_yahoo_returns_none_for_non_equity_or_unknown() -> None:
    assert to_yahoo("TRSKCTFK2610", "corporate_bond") is None
    assert to_yahoo("XYZ ZZ", "equity_foreign") is None


def test_storage_ticker() -> None:
    assert storage_ticker("SAHOL.IS") == "SAHOL"
    assert storage_ticker("ENR.DE") == "ENR.DE"


def test_normalize_history_handles_timezone_and_bad_rows() -> None:
    index = pd.DatetimeIndex(
        ["2026-10-01 00:00", "2026-10-02 00:00", "2026-10-05 00:00"], tz="Europe/Berlin"
    )
    raw = pd.DataFrame(
        {
            "Open": [1.0, 2.0, 3.0],
            "High": [1.0, 2.0, 3.0],
            "Low": [1.0, 2.0, 3.0],
            "Close": [1.0, 0.0, 3.0],
            "Volume": [10, 20, None],
            "Dividends": [0.0, 0.0, 0.0],
        },
        index=index,
    )
    df = normalize_history(raw)
    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert list(df["date"]) == [dt.date(2026, 10, 1), dt.date(2026, 10, 5)]
    assert df["volume"].iloc[-1] == 0


def test_normalize_history_empty() -> None:
    assert normalize_history(pd.DataFrame()).empty
