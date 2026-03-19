from __future__ import annotations

import asyncio
import secrets
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import engine, async_session, Base
from app.models import Agent, Season, Account


AGENTS: list[dict] = []


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # --- Season ---
        existing_season = await db.execute(select(Season).where(Season.id == "2026-Q1"))
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
            existing_us_result = await db.execute(
                select(Account).where(Account.id == us_id)
            )
            existing_us = existing_us_result.scalar_one_or_none()

            # CN account
            cn_id = f"{agent_data['id']}-cn"
            existing_cn_result = await db.execute(
                select(Account).where(Account.id == cn_id)
            )
            existing_cn = existing_cn_result.scalar_one_or_none()

            # 同一 agent 的 US/CN 账户共享 token，与 register_agent 逻辑保持一致
            shared_token = (
                existing_us.api_token
                if existing_us
                else existing_cn.api_token
                if existing_cn
                else secrets.token_hex(32)
            )

            if (
                existing_us
                and existing_cn
                and existing_us.api_token != existing_cn.api_token
            ):
                existing_cn.api_token = shared_token

            # 新规则：总资金 100万人民币，按汇率兑换成美元，剩余为人民币
            total_cny = Decimal(str(settings.total_starting_capital_cny))
            exchange_rate = Decimal(str(settings.exchange_rate))
            usd_amount = (total_cny / exchange_rate).quantize(Decimal("0.01"))
            cny_remaining = total_cny - (usd_amount * exchange_rate)

            if not existing_us:
                us_account = Account(
                    id=us_id,
                    season_id="2026-Q1",
                    agent_id=agent_data["id"],
                    market="us",
                    currency="USD",
                    initial_cash=usd_amount,
                    cash=usd_amount,
                    api_token=shared_token,
                )
                db.add(us_account)

            if not existing_cn:
                cn_account = Account(
                    id=cn_id,
                    season_id="2026-Q1",
                    agent_id=agent_data["id"],
                    market="cn",
                    currency="CNY",
                    initial_cash=cny_remaining.quantize(Decimal("0.01")),
                    cash=cny_remaining.quantize(Decimal("0.01")),
                    api_token=shared_token,
                )
                db.add(cn_account)

        await db.commit()
        print("Season created successfully. No official agents were seeded.")

        # 打印每个 agent 的共享 token，方便 skill/手工调用
        result = await db.execute(
            select(Account).order_by(Account.agent_id, Account.market)
        )
        accounts = result.scalars().all()
        if accounts:
            print(f"\n{'Agent ID':<16} {'Account ID':<20} {'Market':<8} {'Token'}")
            print("-" * 90)
            for acc in accounts:
                print(
                    f"{acc.agent_id:<16} {acc.id:<20} {acc.market:<8} {acc.api_token}"
                )
        else:
            print(
                "Current database has no participant accounts. Players must register their own agents."
            )


if __name__ == "__main__":
    asyncio.run(seed())
