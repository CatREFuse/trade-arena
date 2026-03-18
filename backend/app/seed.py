from __future__ import annotations

import asyncio
import secrets
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, async_session, Base
from app.models import Agent, Season, Account


AGENTS = [
    {
        "id": "opus",
        "name": "深渊之眼",
        "avatar": "\U0001f9e0",
        "model": "claude-opus-4-6",
        "camp": "closed",
        "style": "深度价值 + 长线持有",
        "framework": "claude-code",
    },
    {
        "id": "gemini",
        "name": "星图者",
        "avatar": "\U0001f31f",
        "model": "gemini-3.1-pro",
        "camp": "closed",
        "style": "均衡成长 + 信息广度",
        "framework": "opencode",
    },
    {
        "id": "gpt",
        "name": "闪电手",
        "avatar": "\u26a1",
        "model": "gpt-5.4",
        "camp": "closed",
        "style": "短线趋势交易",
        "framework": "opencode",
    },
    {
        "id": "grok",
        "name": "叛逆者",
        "avatar": "\U0001f525",
        "model": "grok-4.1",
        "camp": "closed",
        "style": "激进投机 + 逆向操作",
        "framework": "opencode",
    },
    {
        "id": "qwen",
        "name": "东方龙",
        "avatar": "\U0001f409",
        "model": "qwen3-max",
        "camp": "open",
        "style": "避险 + 择时",
        "framework": "opencode",
    },
    {
        "id": "deepseek",
        "name": "深思者",
        "avatar": "\U0001f52e",
        "model": "deepseek-v3.2",
        "camp": "open",
        "style": "量化分析 + 稳健",
        "framework": "opencode",
    },
    {
        "id": "glm",
        "name": "智鉴阁",
        "avatar": "\U0001f3db\ufe0f",
        "model": "glm-5",
        "camp": "open",
        "style": "多因子分析",
        "framework": "opencode",
    },
    {
        "id": "kimi",
        "name": "弄潮儿",
        "avatar": "\U0001f30a",
        "model": "kimi-k2.5",
        "camp": "open",
        "style": "代码驱动量化",
        "framework": "opencode",
    },
]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # --- Season ---
        existing_season = await db.execute(
            select(Season).where(Season.id == "2026-Q1")
        )
        if not existing_season.scalar_one_or_none():
            season = Season(
                id="2026-Q1",
                name="第一赛季",
                start_date=date(2026, 3, 18),
            )
            db.add(season)

        # --- Agents & Accounts ---
        for agent_data in AGENTS:
            existing_agent = await db.execute(
                select(Agent).where(Agent.id == agent_data["id"])
            )
            if not existing_agent.scalar_one_or_none():
                agent = Agent(**agent_data)
                db.add(agent)

            # US account
            us_id = f"{agent_data['id']}-us"
            existing_us = await db.execute(
                select(Account).where(Account.id == us_id)
            )
            if not existing_us.scalar_one_or_none():
                us_account = Account(
                    id=us_id,
                    season_id="2026-Q1",
                    agent_id=agent_data["id"],
                    market="us",
                    currency="USD",
                    initial_cash=Decimal("500000"),
                    cash=Decimal("500000"),
                    api_token=secrets.token_hex(32),
                )
                db.add(us_account)

            # CN account
            cn_id = f"{agent_data['id']}-cn"
            existing_cn = await db.execute(
                select(Account).where(Account.id == cn_id)
            )
            if not existing_cn.scalar_one_or_none():
                cn_account = Account(
                    id=cn_id,
                    season_id="2026-Q1",
                    agent_id=agent_data["id"],
                    market="cn",
                    currency="CNY",
                    initial_cash=Decimal("500000"),
                    cash=Decimal("500000"),
                    api_token=secrets.token_hex(32),
                )
                db.add(cn_account)

        await db.commit()
        print("Seed data created successfully!")

        # 打印 tokens
        result = await db.execute(select(Account).order_by(Account.id))
        accounts = result.scalars().all()
        print(f"\n{'Account ID':<20} {'Market':<8} {'Token'}")
        print("-" * 90)
        for acc in accounts:
            print(f"{acc.id:<20} {acc.market:<8} {acc.api_token}")


if __name__ == "__main__":
    asyncio.run(seed())
