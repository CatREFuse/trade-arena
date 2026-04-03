from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, TypeVar

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Account, Agent, AgentEquityPoint, Position, Wallet
from app.schemas import AgentRanking, LeaderboardOut, SparklinePointOut
from app.services.fx import FXService
from app.services.market_data import MarketDataService

T = TypeVar("T")


class RankingService:
    MINI_SPARKLINE_SPAN_DAYS = 3
    MINI_SPARKLINE_POINTS = 72
    SERIES_STEP_MINUTES = 5

    def __init__(
        self,
        db: AsyncSession,
        redis: Redis,
        market_svc: MarketDataService | None = None,
        fx_service: FXService | None = None,
    ):
        self.db = db
        self.redis = redis
        self.market_svc = market_svc or MarketDataService(redis)
        self.fx_service = fx_service or FXService(redis)

    async def _calc_position_value(
        self,
        positions: list[Position],
        quote_map: dict[str, object | None],
    ) -> Decimal:
        total = Decimal("0")
        for pos in positions:
            try:
                quote = quote_map.get(pos.ticker)
                if quote is None:
                    raise LookupError(pos.ticker)
                total += pos.shares * quote.price
            except Exception:
                total += pos.shares * pos.avg_cost
        return total

    async def _rate_to_cny(self, market: str) -> Decimal:
        market_normalized = market.lower()
        if market_normalized == "cn":
            return Decimal("1")
        if market_normalized == "us":
            rate, _, _ = await self.fx_service.get_rate_to_cny("us")
            return Decimal(str(rate))
        if market_normalized == "hk":
            rate, _, _ = await self.fx_service.get_rate_to_cny("hk")
            return Decimal(str(rate))
        return Decimal("1")

    @staticmethod
    def _floor_to_five_minutes(ts: datetime) -> datetime:
        return ts.replace(minute=(ts.minute // 5) * 5, second=0, microsecond=0)

    @staticmethod
    def _downsample(values: list[T], target: int) -> list[T]:
        if not values:
            return []
        if target <= 1:
            return [values[-1]]
        if len(values) <= target:
            return values
        sampled: list[Decimal] = []
        last_index = len(values) - 1
        for i in range(target):
            idx = round(i * last_index / (target - 1))
            sampled.append(values[idx])
        return sampled

    async def _attach_sparklines(
        self,
        rankings: list[AgentRanking],
        initial_by_agent: dict[str, Decimal],
    ) -> None:
        if not rankings:
            return

        end_time = self._floor_to_five_minutes(datetime.utcnow())
        start_time = end_time - timedelta(days=self.MINI_SPARKLINE_SPAN_DAYS)
        step_seconds = self.SERIES_STEP_MINUTES * 60
        total_steps = int((end_time - start_time).total_seconds() // step_seconds) + 1
        total_steps = max(total_steps, 2)

        agent_ids = [item.agent_id for item in rankings]
        points_result = await self.db.execute(
            select(
                AgentEquityPoint.agent_id,
                AgentEquityPoint.point_time,
                AgentEquityPoint.equity_cny,
            )
            .where(
                AgentEquityPoint.agent_id.in_(agent_ids),
                AgentEquityPoint.point_time >= start_time,
                AgentEquityPoint.point_time <= end_time,
            )
            .order_by(AgentEquityPoint.agent_id, AgentEquityPoint.point_time)
        )

        points_by_agent: dict[str, dict[int, Decimal]] = {}
        for agent_id, point_time, equity_cny in points_result.all():
            idx = int((point_time - start_time).total_seconds() // step_seconds)
            if 0 <= idx < total_steps:
                points_by_agent.setdefault(agent_id, {})[idx] = Decimal(equity_cny)

        for ranking in rankings:
            baseline = initial_by_agent.get(
                ranking.agent_id,
                Decimal(str(settings.total_starting_capital_cny)),
            )
            indexed_points = points_by_agent.get(ranking.agent_id, {})
            dense: list[Decimal] = []
            prev = baseline
            for i in range(total_steps):
                value = indexed_points.get(i)
                if value is None:
                    value = prev
                else:
                    prev = value
                dense.append(value)

            sampled = self._downsample(dense, self.MINI_SPARKLINE_POINTS)
            sampled_times = self._downsample(
                [start_time + timedelta(seconds=step_seconds * i) for i in range(total_steps)],
                self.MINI_SPARKLINE_POINTS,
            )
            ranking.sparkline_3d = [
                SparklinePointOut(
                    time=sampled_times[idx].isoformat(),
                    value=float(sampled[idx]),
                )
                for idx in range(min(len(sampled), len(sampled_times)))
            ]

    async def get_leaderboard(self, market: str = "overall") -> LeaderboardOut:
        db = self.db

        agents_result = await db.execute(select(Agent))
        agents = {a.id: a for a in agents_result.scalars().all()}

        accounts_result = await db.execute(select(Account))
        accounts = accounts_result.scalars().all()

        wallets_result = await db.execute(select(Wallet))
        wallets = {wallet.agent_id: wallet for wallet in wallets_result.scalars().all()}

        positions_result = await db.execute(select(Position))
        all_positions = positions_result.scalars().all()
        pos_by_account: dict[str, list[Position]] = {}
        for pos in all_positions:
            pos_by_account.setdefault(pos.account_id, []).append(pos)

        quote_map = await self.market_svc.get_quotes_batch(
            list({pos.ticker for pos in all_positions})
        )

        rate_to_cny = {
            "us": await self._rate_to_cny("us"),
            "cn": Decimal("1"),
            "hk": await self._rate_to_cny("hk"),
        }
        usd_to_cny = rate_to_cny["us"] if rate_to_cny["us"] else Decimal(str(settings.exchange_rate))

        agent_accounts: dict[str, list[Account]] = {}
        for acc in accounts:
            agent_accounts.setdefault(acc.agent_id, []).append(acc)

        rankings: list[AgentRanking] = []
        initial_by_agent: dict[str, Decimal] = {}

        for agent_id, agent in agents.items():
            accs = agent_accounts.get(agent_id, [])
            markets_for_agent = {acc.market for acc in accs}
            market_assets_cny: dict[str, Decimal] = {
                "us": Decimal("0"),
                "cn": Decimal("0"),
                "hk": Decimal("0"),
            }
            market_cash_cny: dict[str, Decimal] = {
                "us": Decimal("0"),
                "cn": Decimal("0"),
                "hk": Decimal("0"),
            }

            for acc in accs:
                positions = pos_by_account.get(acc.id, [])
                pos_value_local = await self._calc_position_value(positions, quote_map)
                fx = rate_to_cny.get(acc.market, Decimal("1"))
                market_assets_cny[acc.market] = market_assets_cny.get(acc.market, Decimal("0")) + (pos_value_local * fx)
                market_cash_cny[acc.market] = market_cash_cny.get(acc.market, Decimal("0")) + (acc.cash * fx)

            wallet = wallets.get(agent_id)
            if wallet is not None:
                total_initial_cny = wallet.initial_cash
                total_asset_cny = wallet.cash + sum(market_assets_cny.values())
            else:
                total_initial_cny = Decimal(str(settings.total_starting_capital_cny))
                total_asset_cny = sum(market_assets_cny.values()) + sum(market_cash_cny.values())
            initial_by_agent[agent_id] = total_initial_cny

            return_pct = (
                float((total_asset_cny - total_initial_cny) / total_initial_cny * 100)
                if total_initial_cny
                else 0.0
            )

            if market != "overall" and market not in markets_for_agent:
                continue

            total_asset_usd: Optional[Decimal] = None
            if usd_to_cny > Decimal("0"):
                total_asset_usd = total_asset_cny / usd_to_cny

            us_asset_cny = market_assets_cny.get("us", Decimal("0"))
            cn_asset_cny = market_assets_cny.get("cn", Decimal("0"))
            hk_asset_cny = market_assets_cny.get("hk", Decimal("0"))

            rankings.append(
                AgentRanking(
                    agent_id=agent_id,
                    name=agent.name,
                    avatar=agent.avatar,
                    model=agent.model,
                    camp=agent.camp,
                    total_asset_cny=total_asset_cny,
                    total_asset_usd=total_asset_usd,
                    return_pct=round(return_pct, 2),
                    rank=0,
                    us_asset_cny=us_asset_cny,
                    cn_asset_cny=cn_asset_cny,
                    hk_asset_cny=hk_asset_cny,
                    us_asset=(us_asset_cny / usd_to_cny) if usd_to_cny > Decimal("0") else None,
                    cn_asset_usd=(cn_asset_cny / usd_to_cny) if usd_to_cny > Decimal("0") else None,
                )
            )

        if market == "overall":
            rankings.sort(key=lambda r: r.total_asset_cny, reverse=True)
        elif market == "us":
            rankings.sort(
                key=lambda r: (
                    r.us_asset_cny or Decimal("0"),
                    r.total_asset_cny,
                ),
                reverse=True,
            )
        elif market == "cn":
            rankings.sort(
                key=lambda r: (
                    r.cn_asset_cny or Decimal("0"),
                    r.total_asset_cny,
                ),
                reverse=True,
            )
        elif market == "hk":
            rankings.sort(
                key=lambda r: (
                    r.hk_asset_cny or Decimal("0"),
                    r.total_asset_cny,
                ),
                reverse=True,
            )
        else:
            rankings.sort(key=lambda r: r.total_asset_cny, reverse=True)
        for i, r in enumerate(rankings):
            r.rank = i + 1

        await self._attach_sparklines(rankings, initial_by_agent)
        return LeaderboardOut(
            market=market,
            rankings=rankings,
            timestamp=datetime.utcnow(),
        )
