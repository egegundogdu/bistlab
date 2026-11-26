"""Veritabanı bağlantısı ve tablo tanımları."""

from __future__ import annotations

import datetime as dt
import os

from dotenv import load_dotenv
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    create_engine,
    func,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class Security(Base):
    """Borsada işlem gören bir menkul kıymet (ör. THYAO)."""

    __tablename__ = "securities"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str | None] = mapped_column(String(200))


class Price(Base):
    """Bir menkul kıymetin günlük fiyat kaydı."""

    __tablename__ = "prices"

    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id"), primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(20), server_default="yfinance")
    fetched_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def get_engine(url: str | None = None) -> Engine:
    """Verilen URL'ye ya da .env'deki DATABASE_URL'ye bağlanır."""
    load_dotenv()
    database_url = url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL tanımlı değil. .env dosyasını kontrol et.")
    return create_engine(database_url)


def init_db(engine: Engine) -> None:
    """Tabloları oluşturur; zaten varsa dokunmaz."""
    Base.metadata.create_all(engine)


class MacroObservation(Base):
    """TCMB EVDS'den bir makro serinin tek gözlemi (ör. USD/TRY, TÜFE)."""

    __tablename__ = "macro_observations"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    value: Mapped[float] = mapped_column(Float)


class FinancialItem(Base):
    """Finansal tablodaki tek bir kalem (ör. THYAO, 2025 yıllık, gelir tablosu, EBITDA)."""

    __tablename__ = "financial_items"

    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id"), primary_key=True)
    period_end: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    statement: Mapped[str] = mapped_column(String(16), primary_key=True)
    item: Mapped[str] = mapped_column(String(128), primary_key=True)
    source: Mapped[str] = mapped_column(String(16), primary_key=True)
    value: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3))


class Fund(Base):
    """TEFAS'ta işlem gören bir yatırım fonu (ör. IKP)."""

    __tablename__ = "funds"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)
    name: Mapped[str | None] = mapped_column(String(300))


class FundPrice(Base):
    """Fonun günlük birim pay fiyatı."""

    __tablename__ = "fund_prices"

    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id"), primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    price: Mapped[float] = mapped_column(Float)


class FundHolding(Base):
    """Aylık portföy dağılım raporundaki tek bir varlık (hisse, tahvil, BYF, repo...)."""

    __tablename__ = "fund_holdings"

    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id"), primary_key=True)
    report_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    asset: Mapped[str] = mapped_column(String(120), primary_key=True)  # kod ya da ad
    asset_type: Mapped[str] = mapped_column(String(40))  # hisse, tahvil, byf, repo...
    weight: Mapped[float] = mapped_column(Float)  # portföy payı, 0-1
    market_value: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(3))
    isin: Mapped[str | None] = mapped_column(String(12))


def get_or_create_security(session: Session, ticker: str) -> Security:
    """Hisse kaydını bulur; yoksa oluşturur."""
    code = ticker.strip().upper().removesuffix(".IS")
    security = session.scalar(select(Security).where(Security.ticker == code))
    if security is None:
        security = Security(ticker=code)
        session.add(security)
        session.flush()
    return security
