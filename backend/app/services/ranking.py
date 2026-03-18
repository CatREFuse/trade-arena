from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.models import Agent, Account, Position
from app.schemas import AgentRanking, LeaderboardOut
from app.services.market_data import MarketDataService

CNY_TO_USD = Decimal("0.137")


class RankingService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.market_svc = MarketDataService(redis)

    async def _calc_position_value(self, positions: list[Position]) -> Decimal:
        total = Decimal("0")
        for pos in positions:
            try:
                quote = await self.market_svc.get_quote(pos.ticker)
                total += pos.shares * quote.price
            except Exception:
                total += pos.shares * pos.avg_cost
        return total

    async def get_leaderboard(self, market: str = "overall") -> LeaderboardOut:
        db = self.db

        agents_result = await db.execute(select(Agent))
        agents = {a.id: a for a in agents_result.scalars().all()}

        accounts_result = await db.execute(select(Account))
        accounts = accounts_result.scalars().all()

        positions_result = await db.execute(select(Position))
        all_positions = positions_result.scalars().all()

        # 按 account_id 分组持仓
        pos_by_account: dict[str, list[Position]] = {}
        for pos in all_positions:
            pos_by_account.setdefault(pos.account_id, []).append(pos)

        # 按 agent_id 分组 accounts
        agent_accounts: dict[str, list[Account]] = {}
        for acc in accounts:
            agent_accounts.setdefault(acc.agent_id, []).append(acc)

        rankings: list[AgentRanking] = []

        for agent_id, agent in agents.items():
            accs = agent_accounts.get(agent_id, [])
            us_asset: Optional[Decimal] = None
            cn_asset_usd: Optional[Decimal] = None
            total_initial_usd = Decimal("0")

            for acc in accs:
                positions = pos_by_account.get(acc.id, [])
                pos_value = await self._calc_position_value(positions)
                asset = acc.cash + pos_value

                if acc.market == "us":
                    us_asset = asset
                    total_initial_usd += acc.initial_cash
                elif acc.market == "cn":
                    cn_asset_usd = asset * CNY_TO_USD
                    total_initial_usd += acc.initial_cash * CNY_TO_USD

            total_asset_usd = (us_asset or Decimal("0")) + (cn_asset_usd or Decimal("0"))
            return_pct = (
                float((total_asset_usd - total_initial_usd) / total_initial_usd * 100)
                if total_initial_usd
                else 0.0
            )

            # 按 market 过滤
            if market == "us" and us_asset is None:
                continue
            if market == "cn" and cn_asset_usd is None:
                continue

            rankings.append(
                AgentRanking(
                    agent_id=agent_id,
                    name=agent.name,
                    avatar=agent.avatar,
                    model=agent.model,
                    camp=agent.camp,
                    total_asset_usd=total_asset_usd,
                    return_pct=round(return_pct, 2),
                    rank=0,
                    us_asset=us_asset,
                    cn_asset_usd=cn_asset_usd,
                )
            )

        # 排序并赋 rank
        rankings.sort(key=lambda r: r.total_asset_usd, reverse=True)
        for i, r in enumerate(rankings):
            r.rank = i + 1

        return LeaderboardOut(market=market, rankings=rankings)
