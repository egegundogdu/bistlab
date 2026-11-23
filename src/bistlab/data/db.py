"""Veritabanı bağlantısı ve tablo tanımları."""

from __future__ import annotations

import datetime as dt
import os

from dotenv import load_dotenv
from sqlalchemy import BigInteger, Date, Float, ForeignKey, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
