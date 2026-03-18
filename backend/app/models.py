from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    avatar: Mapped[str] = mapped_column(String(10))
    model: Mapped[str] = mapped_column(String(50))
    camp: Mapped[str] = mapped_column(String(10))
    style: Mapped[str] = mapped_column(String(100))
    framework: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    season_id: Mapped[str] = mapped_column(ForeignKey("seasons.id"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    market: Mapped[str] = mapped_column(String(5))
    currency: Mapped[str] = mapped_column(String(5))
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    cash: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    api_token: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    ticker: Mapped[str] = mapped_column(String(20))
    shares: Mapped[Decimal] = mapped_column(Numeric(15, 6))
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(15, 4))
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (UniqueConstraint("account_id", "ticker"),)


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    ticker: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(10))
    shares: Mapped[Decimal] = mapped_column(Numeric(15, 6))
    price: Mapped[Decimal] = mapped_column(Numeric(15, 4))
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    fee: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning_full: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    date: Mapped[date] = mapped_column(Date)
    total_asset: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    cash: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    position_value: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    trade_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("account_id", "date"),)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(20))
    agent_id: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
