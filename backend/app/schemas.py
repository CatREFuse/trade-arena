from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class APIModel(BaseModel):
    model_config = ConfigDict()

    @field_serializer("*", when_used="json", check_fields=False)
    def serialize_datetimes_as_utc(self, value):
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                return value.replace(tzinfo=timezone.utc).isoformat()
            return value.astimezone(timezone.utc).isoformat()
        return value


# --- Account ---
class AccountCreate(APIModel):
    agent_id: str
    market: str


class AccountOut(APIModel):
    id: str
    agent_id: str
    market: str
    currency: str
    initial_cash: Decimal
    cash: Decimal
    available_cash_cny: Decimal


class PositionOut(APIModel):
    ticker: str
    shares: Decimal
    avg_cost: Decimal
    current_price: Optional[Decimal] = None
    pnl: Optional[Decimal] = None
    pnl_cny: Optional[Decimal] = None
    weight: Optional[float] = None


class PortfolioOut(APIModel):
    cash: Decimal
    cash_currency: str = "CNY"
    fx_pair: Optional[str] = None
    fx_rate: Optional[Decimal] = None
    fx_updated_at: Optional[datetime] = None
    positions: list[PositionOut]


class PublicPositionOut(APIModel):
    ticker: str
    shares: Decimal
    avg_cost_cny: Decimal
    current_price_cny: Optional[Decimal] = None
    pnl_cny: Optional[Decimal] = None
    market_value_cny: Decimal


class AgentMarketPortfolioOut(APIModel):
    market: str
    account_id: Optional[str] = None
    holdings_count: int
    position_value_cny: Decimal
    positions: list[PublicPositionOut]


class AgentPortfolioSummaryOut(APIModel):
    agent_id: str
    wallet_cash_cny: Decimal
    total_asset_cny: Decimal
    markets: list[AgentMarketPortfolioOut]
    updated_at: datetime


# --- Trade ---
class BuyRequest(APIModel):
    account_id: Optional[str] = None
    market: Optional[str] = None  # "us" | "cn"，与 token 配合自动解析 account_id
    ticker: str
    amount: Decimal = Field(gt=0)
    reasoning: Optional[str] = None
    reasoning_full: Optional[str] = None
    idempotency_key: Optional[str] = None


class SellRequest(APIModel):
    account_id: Optional[str] = None
    market: Optional[str] = None
    ticker: str
    shares: Decimal = Field(gt=0)
    reasoning: Optional[str] = None
    reasoning_full: Optional[str] = None
    idempotency_key: Optional[str] = None


class TradeOut(APIModel):
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
class QuoteOut(APIModel):
    ticker: str
    price: Decimal
    change_pct: float
    name: Optional[str] = None
    volume: Optional[int] = None
    market_status: str


class IndexQuoteOut(APIModel):
    """大盘指数行情"""
    symbol: str
    name: str
    price: float
    change_pct: float
    market: str


class MarketBoardItemOut(APIModel):
    ticker: str
    name: str
    market: str
    price: Decimal
    change_pct: float
    volume: Optional[int] = None
    market_status: str


class MarketBoardSnapshotOut(APIModel):
    items: list[MarketBoardItemOut]
    updated_at: datetime


class MarketSummaryOut(APIModel):
    market: str
    name: str
    stock_count: int
    up_count: int
    down_count: int
    flat_count: int
    avg_change_pct: float
    leader: Optional[MarketBoardItemOut] = None
    laggard: Optional[MarketBoardItemOut] = None


class MarketOverviewOut(APIModel):
    indices: list[IndexQuoteOut]
    boards: dict[str, list[MarketBoardItemOut]]
    markets: list[MarketSummaryOut]
    updated_at: datetime


class MarketTrendPointOut(APIModel):
    ts: int
    close: float


class MarketTrendOut(APIModel):
    market: str
    symbol: str
    name: str
    points: list[MarketTrendPointOut]
    updated_at: datetime


class FXHistoryPointOut(APIModel):
    ts: int
    rate: float


class FXPairSnapshotOut(APIModel):
    pair: str
    base: str
    quote: str
    rate: float
    change_pct_24h: float
    points: list[FXHistoryPointOut]
    source: Optional[str] = None
    history_source: Optional[str] = None
    updated_at: Optional[datetime] = None


class MarketFXOverviewOut(APIModel):
    pairs: list[FXPairSnapshotOut]
    updated_at: datetime


class StockHistoryPointOut(APIModel):
    ts: int
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None


class StockIntradayPointOut(APIModel):
    ts: int
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None


class StockIntradayOut(APIModel):
    ticker: str
    interval: str
    span: str
    points: list[StockIntradayPointOut]
    source: Optional[str] = None
    updated_at: datetime


class StockSiteStatsOut(APIModel):
    total_trade_count: int
    buy_trade_count: int
    sell_trade_count: int
    total_amount: Decimal
    total_amount_cny: Decimal
    unique_agent_count: int
    last_trade_at: Optional[datetime] = None


class StockRecentTradeOut(APIModel):
    trade_id: int
    agent_id: str
    agent_name: str
    agent_avatar: str
    market: str
    action: str
    shares: Decimal
    price: Decimal
    amount: Decimal
    amount_cny: Optional[Decimal] = None
    reasoning: Optional[str] = None
    created_at: datetime


class StockPositionStatsOut(APIModel):
    holder_count: int
    total_shares: Decimal
    market_value: Optional[Decimal] = None
    market_value_cny: Optional[Decimal] = None
    fx_pair: Optional[str] = None
    fx_rate: Optional[Decimal] = None


class StockDetailOut(APIModel):
    ticker: str
    name: Optional[str] = None
    market: str
    days: int
    listed_at: Optional[str] = None
    quote: QuoteOut
    history: list[StockHistoryPointOut]
    history_source: Optional[str] = None
    site_stats: StockSiteStatsOut
    recent_trades: list[StockRecentTradeOut]
    position_stats: StockPositionStatsOut
    updated_at: datetime


class SparklinePointOut(APIModel):
    time: str
    value: float


class ChartPointOut(APIModel):
    """资产曲线数据点"""
    date: str
    value: float


class AgentEquityCurveOut(APIModel):
    span: str
    interval: str
    points: list[ChartPointOut]


# --- Leaderboard ---
class AgentRanking(APIModel):
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
    sparkline_3d: list[SparklinePointOut] = Field(default_factory=list)


class LeaderboardOut(APIModel):
    market: str
    rankings: list[AgentRanking]
    timestamp: datetime


# --- Feed ---
class FeedItem(APIModel):
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
class SnapshotOut(APIModel):
    date: date
    total_asset: Decimal
    cash: Decimal
    position_value: Decimal


class SkillVersionOut(APIModel):
    version: str
    hosted_url: str



# --- Agent Registration ---
class AgentOut(APIModel):
    id: str
    name: str
    avatar: str
    model: str
    camp: str
    style: str
    framework: str
    created_at: datetime


class AgentRegisterRequest(APIModel):
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


class AgentRegisterResponse(APIModel):
    agent: AgentOut
    token: str


class AgentEmailCodeRequest(APIModel):
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


class AgentEmailCodeResponse(APIModel):
    email: str
    expires_in: int
    cooldown_in: int
    delivery: str
    dev_code: Optional[str] = None
