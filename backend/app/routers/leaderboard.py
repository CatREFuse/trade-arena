from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Trade, Agent, Account
from app.schemas import LeaderboardOut, FeedItem
from app.services.ranking import RankingService

router = APIRouter(prefix="/api", tags=["leaderboard"])
logger = logging.getLogger(__name__)


@router.get("/leaderboard", response_model=LeaderboardOut)
async def leaderboard(
    request: Request,
    market: str = "overall",
    include_empty: bool = True,
    include_sparkline: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """获取排行榜"""
    try:
        redis = request.app.state.redis
        market_svc = getattr(request.app.state, "market_data_service", None)
        svc = RankingService(db, redis, market_svc=market_svc)
        return await svc.get_leaderboard(
            market,
            include_empty=include_empty,
            include_sparkline=include_sparkline,
        )
    except SQLAlchemyError as e:
        logger.error(f"[GET /api/leaderboard] DB_ERROR: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "DATABASE_UNAVAILABLE",
                "message": "数据库暂时不可用，请稍后重试",
            },
        )
    except Exception as e:
        logger.error(f"[GET /api/leaderboard] UNEXPECTED_ERROR: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "SERVICE_UNAVAILABLE",
                "message": "服务暂时不可用，请稍后重试",
            },
        )


@router.get("/feed", response_model=list[FeedItem])
async def feed(
    limit: int = 20,
    offset: int = 0,
    agent_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """获取交易动态"""
    try:
        query = select(Trade)
        if agent_id:
            query = (
                query
                .join(Account, Account.id == Trade.account_id)
                .where(Account.agent_id == agent_id)
            )

        result = await db.execute(query.order_by(Trade.created_at.desc()).limit(limit).offset(offset))
        trades = result.scalars().all()

        if not trades:
            return []

        account_ids = {trade.account_id for trade in trades}
        account_rows = await db.execute(select(Account).where(Account.id.in_(account_ids)))
        account_map = {account.id: account for account in account_rows.scalars().all()}

        agent_ids = set()
        trade_list: list[tuple[Trade, str]] = []
        for t in trades:
            account = account_map.get(t.account_id)
            if account is None:
                continue
            resolved_agent_id = account.agent_id
            agent_ids.add(resolved_agent_id)
            trade_list.append((t, resolved_agent_id))

        agents_result = await db.execute(
            select(Agent).where(Agent.id.in_(agent_ids), Agent.is_deleted.is_(False))
        )
        agents = {a.id: a for a in agents_result.scalars().all()}

        items: list[FeedItem] = []
        for t, agent_id in trade_list:
            agent = agents.get(agent_id)
            if not agent:
                continue
            items.append(
                FeedItem(
                    id=t.id,
                    type="trade",
                    agent_id=agent_id,
                    agent_name=agent.name,
                    agent_avatar=agent.avatar,
                    action=t.action,
                    ticker=t.ticker,
                    shares=t.shares,
                    price=t.price,
                    amount=t.amount,
                    reasoning=t.reasoning,
                    created_at=t.created_at,
                )
            )

        return items
    except SQLAlchemyError as e:
        logger.error(f"[GET /api/feed] DB_ERROR: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "DATABASE_UNAVAILABLE",
                "message": "数据库暂时不可用，请稍后重试",
            },
        )
    except Exception as e:
        logger.error(f"[GET /api/feed] UNEXPECTED_ERROR: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "SERVICE_UNAVAILABLE",
                "message": "服务暂时不可用，请稍后重试",
            },
        )
