import datetime as dt

from sqlalchemy.orm import Session

from bistlab.data.db import Price, Security, get_engine, init_db


def test_security_and_price_roundtrip() -> None:
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        security = Security(ticker="TEST", name="Test Inc.")
        session.add(security)
        session.flush()
        session.add(
            Price(
                security_id=security.id,
                date=dt.date(2026, 1, 2),
                open=10.0,
                high=11.0,
                low=9.5,
                close=10.5,
                volume=1000,
            )
        )
        session.commit()

        stored = session.get(Price, (security.id, dt.date(2026, 1, 2)))
        assert stored is not None
        assert stored.close == 10.5
