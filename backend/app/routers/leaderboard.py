from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Trade, Agent
from app.schemas import LeaderboardOut, FeedItem
from app.services.ranking import RankingService

router = APIRouter(prefix="/api", tags=["leaderboard"])
logger = logging.getLogger(__name__)


@router.get("/leaderboard", response_model=LeaderboardOut)
async def leaderboard(
    request: Request,
    market: str = "overall",
    db: AsyncSession = Depends(get_db),
):
    """获取排行榜"""
    try:
        redis = request.app.state.redis
        svc = RankingService(db, redis)
        return await svc.get_leaderboard(market)
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
    db: AsyncSession = Depends(get_db),
):
    """获取交易动态"""
    try:
        result = await db.execute(
            select(Trade)
            .order_by(Trade.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        trades = result.scalars().all()

        # 批量获取 agent 信息
        agent_ids = set()
        trade_list = []
        for t in trades:
            # account_id 格式为 "{agent_id}-us" 或 "{agent_id}-cn"
            agent_id = t.account_id.rsplit("-", 1)[0]
            agent_ids.add(agent_id)
            trade_list.append((t, agent_id))

        agents_result = await db.execute(
            select(Agent).where(Agent.id.in_(agent_ids))
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
