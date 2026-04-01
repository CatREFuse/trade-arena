from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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
    available_cash_cny: Decimal


class PositionOut(BaseModel):
    ticker: str
    shares: Decimal
    avg_cost: Decimal
    current_price: Optional[Decimal] = None
    pnl: Optional[Decimal] = None
    pnl_cny: Optional[Decimal] = None
    weight: Optional[float] = None


class PortfolioOut(BaseModel):
    cash: Decimal
    cash_currency: str = "CNY"
    fx_pair: Optional[str] = None
    fx_rate: Optional[Decimal] = None
    fx_updated_at: Optional[datetime] = None
    positions: list[PositionOut]


# --- Trade ---
class BuyRequest(BaseModel):
    account_id: Optional[str] = None
    market: Optional[str] = None  # "us" | "cn"，与 token 配合自动解析 account_id
    ticker: str
    amount: Decimal = Field(gt=0)
    reasoning: Optional[str] = None
    reasoning_full: Optional[str] = None
    idempotency_key: Optional[str] = None


class SellRequest(BaseModel):
    account_id: Optional[str] = None
    market: Optional[str] = None
    ticker: str
    shares: Decimal = Field(gt=0)
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
    fx_pair: Optional[str] = None
    fx_rate: Optional[Decimal] = None
    amount_cny: Optional[Decimal] = None
    fee_cny: Optional[Decimal] = None
    cash_after_cny: Optional[Decimal] = None
    created_at: datetime


# --- Market ---
class QuoteOut(BaseModel):
    ticker: str
    price: Decimal
    change_pct: float
    name: Optional[str] = None
    volume: Optional[int] = None
    market_status: str


class IndexQuoteOut(BaseModel):
    """大盘指数行情"""
    symbol: str
    name: str
    price: float
    change_pct: float
    market: str


class MarketBoardItemOut(BaseModel):
    ticker: str
    name: str
    market: str
    price: Decimal
    change_pct: float
    volume: Optional[int] = None
    market_status: str


class MarketBoardSnapshotOut(BaseModel):
    items: list[MarketBoardItemOut]
    updated_at: datetime


class MarketSummaryOut(BaseModel):
    market: str
    name: str
    stock_count: int
    up_count: int
    down_count: int
    flat_count: int
    avg_change_pct: float
    leader: Optional[MarketBoardItemOut] = None
    laggard: Optional[MarketBoardItemOut] = None


class MarketOverviewOut(BaseModel):
    indices: list[IndexQuoteOut]
    boards: dict[str, list[MarketBoardItemOut]]
    markets: list[MarketSummaryOut]
    updated_at: datetime


# --- Leaderboard ---
class AgentRanking(BaseModel):
    agent_id: str
    name: str
    avatar: str
    model: str
    camp: str
    total_asset_cny: Decimal
    total_asset_usd: Optional[Decimal] = None  # legacy compatibility
    return_pct: float
    rank: int
    us_asset_cny: Optional[Decimal] = None
    cn_asset_cny: Optional[Decimal] = None
    hk_asset_cny: Optional[Decimal] = None
    us_asset: Optional[Decimal] = None  # legacy compatibility
    cn_asset_usd: Optional[Decimal] = None  # legacy compatibility


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


class ChartPointOut(BaseModel):
    """资产曲线数据点"""
    date: str
    value: float


class SkillVersionOut(BaseModel):
    version: str
    hosted_url: str



# --- Agent Registration ---
class AgentOut(BaseModel):
    id: str
    name: str
    avatar: str
    model: str
    camp: str
    style: str
    framework: str
    created_at: datetime


class AgentRegisterRequest(BaseModel):
    name: str
    email: str
    model: str
    avatar: str
    style: str
    framework: str = "custom"

    @field_validator("name")
    @classmethod
    def name_check(cls, v):
        v = v.strip()
        if not v or len(v) > 50:
            raise ValueError("名称长度需在 1-50 字符之间")
        return v

    @field_validator("email")
    @classmethod
    def email_check(cls, v):
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("请输入有效邮箱")
        if len(v) > 255:
            raise ValueError("邮箱长度不能超过 255 字符")
        return v

    @field_validator("avatar")
    @classmethod
    def avatar_check(cls, v):
        v = v.strip()
        if not v or len(v) > 10:
            raise ValueError("请输入一个 emoji 作为头像")
        return v

    @field_validator("model")
    @classmethod
    def model_check(cls, v):
        v = v.strip()
        if not v or len(v) > 50:
            raise ValueError("模型名称长度需在 1-50 字符之间")
        return v

    @field_validator("style")
    @classmethod
    def style_check(cls, v):
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError("投资风格描述长度需在 1-100 字符之间")
        return v


class AgentRegisterResponse(BaseModel):
    agent: AgentOut
    token: str


class AgentEmailCodeRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def email_check(cls, v):
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("请输入有效邮箱")
        if len(v) > 255:
            raise ValueError("邮箱长度不能超过 255 字符")
        return v


class AgentEmailCodeResponse(BaseModel):
    email: str
    expires_in: int
    cooldown_in: int
    delivery: str
    dev_code: Optional[str] = None
