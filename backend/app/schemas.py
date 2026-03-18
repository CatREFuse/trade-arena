from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


# --- Account ---
class AccountCreate(BaseModel):
    agent_id: str
    market: str


class AccountOut(BaseModel):
    id: str
    agent_id: str
    market: str
    currency: str
    initial_cash: Decimal
    cash: Decimal


class PositionOut(BaseModel):
    ticker: str
    shares: Decimal
    avg_cost: Decimal
    current_price: Optional[Decimal] = None
    pnl: Optional[Decimal] = None
    weight: Optional[float] = None


class PortfolioOut(BaseModel):
    cash: Decimal
    positions: list[PositionOut]


# --- Trade ---
class BuyRequest(BaseModel):
    account_id: str
    ticker: str
    amount: Decimal
    reasoning: Optional[str] = None
    reasoning_full: Optional[str] = None
    idempotency_key: Optional[str] = None


class SellRequest(BaseModel):
    account_id: str
    ticker: str
    shares: Decimal
    reasoning: Optional[str] = None
    reasoning_full: Optional[str] = None
    idempotency_key: Optional[str] = None


class TradeOut(BaseModel):
    trade_id: int
    ticker: str
    action: str
    shares: Decimal
    price: Decimal
    amount: Decimal
    fee: Decimal
    cash_after: Decimal
    created_at: datetime


# --- Market ---
class QuoteOut(BaseModel):
    ticker: str
    price: Decimal
    change_pct: float
    volume: Optional[int] = None
    market_status: str


# --- Leaderboard ---
class AgentRanking(BaseModel):
    agent_id: str
    name: str
    avatar: str
    model: str
    camp: str
    total_asset_usd: Decimal
    return_pct: float
    rank: int
    us_asset: Optional[Decimal] = None
    cn_asset_usd: Optional[Decimal] = None


class LeaderboardOut(BaseModel):
    market: str
    rankings: list[AgentRanking]


# --- Feed ---
class FeedItem(BaseModel):
    id: int
    type: str
    agent_id: str
    agent_name: str
    agent_avatar: str
    action: str
    ticker: str
    shares: Decimal
    price: Decimal
    amount: Decimal
    reasoning: Optional[str] = None
    created_at: datetime


# --- Snapshot ---
class SnapshotOut(BaseModel):
    date: date
    total_asset: Decimal
    cash: Decimal
    position_value: Decimal
