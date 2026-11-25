import datetime as dt

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bistlab.data.db import FundHolding, FundPrice, get_engine, init_db
from bistlab.funds.tefas import get_or_create_fund, normalize_fund_prices, save_fund_prices


def _raw() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Code": ["IKP", "IKP", "IKP", "IKP"],
            "Date": ["2026-01-05", "2026-01-02", "2026-01-05", "2026-01-06"],
            "Price": [8.10, 8.00, 8.12, 0.0],
        }
    )


def test_normalize_sorts_dedupes_and_drops_zero_prices() -> None:
    df = normalize_fund_prices(_raw())
    assert list(df["date"]) == [dt.date(2026, 1, 2), dt.date(2026, 1, 5)]
    assert list(df["price"]) == [8.00, 8.12]  # aynı gün: sonuncu tutulur; sıfır fiyat atılır


def test_save_fund_prices_twice_does_not_duplicate() -> None:
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    prices = normalize_fund_prices(_raw())
    with Session(engine) as session:
        save_fund_prices(session, "ikp", prices)
        save_fund_prices(session, "IKP", prices)
        assert session.scalar(select(func.count()).select_from(FundPrice)) == 2


def test_fund_holding_supports_non_equity_assets() -> None:
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        fund = get_or_create_fund(session, "IKP")
        session.add_all(
            [
                FundHolding(
                    fund_id=fund.id,
                    report_date=dt.date(2026, 10, 31),
                    asset="ENJSA",
                    asset_type="hisse",
                    weight=0.08,
                    market_value=1_000_000.0,
                    currency="TRY",
                ),
                FundHolding(
                    fund_id=fund.id,
                    report_date=dt.date(2026, 10, 31),
                    asset="ICLN",
                    asset_type="yabancı byf",
                    weight=0.05,
                    market_value=None,
                    currency="USD",
                ),
            ]
        )
        session.commit()
        assert session.scalar(select(func.count()).select_from(FundHolding)) == 2
