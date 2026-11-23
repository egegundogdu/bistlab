import datetime as dt

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bistlab.data.db import FinancialItem, get_engine, init_db
from bistlab.data.financials import save_financials, to_long


def _sample() -> pd.DataFrame:
    return pd.DataFrame(
        {
            pd.Timestamp("2025-12-31"): [100.0, 40.0],
            pd.Timestamp("2024-12-31"): [90.0, float("nan")],
        },
        index=["Total Revenue", "EBITDA"],
    )


def test_to_long_skips_missing_values() -> None:
    rows = to_long(_sample(), "income")
    assert sorted(rows) == sorted(
        [
            (dt.date(2025, 12, 31), "income", "Total Revenue", 100.0),
            (dt.date(2024, 12, 31), "income", "Total Revenue", 90.0),
            (dt.date(2025, 12, 31), "income", "EBITDA", 40.0),
        ]
    )


def test_save_financials_stores_currency_and_does_not_duplicate() -> None:
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    rows = to_long(_sample(), "income")
    with Session(engine) as session:
        save_financials(session, "TEST", rows, "USD")
        save_financials(session, "TEST", rows, "USD")
        count = session.scalar(select(func.count()).select_from(FinancialItem))
        currencies = set(session.scalars(select(FinancialItem.currency)))
    assert count == 3
    assert currencies == {"USD"}
