from __future__ import annotations

import asyncio
import secrets
from decimal import Decimal

from sqlalchemy import select

from app.config import settings
from app.database import engine, async_session, Base
from app.models import Agent, Account, Wallet


AGENTS: list[dict] = []


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
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

            # HK account
            hk_id = f"{agent_data['id']}-hk"
            existing_hk_result = await db.execute(
                select(Account).where(Account.id == hk_id)
            )
            existing_hk = existing_hk_result.scalar_one_or_none()

            # 同一 agent 的 US/CN/HK 账户共享 token，与 register_agent 逻辑保持一致
            shared_token = (
                existing_us.api_token
                if existing_us
                else existing_cn.api_token
                if existing_cn
                else existing_hk.api_token
                if existing_hk
                else secrets.token_hex(32)
            )

            if (
                existing_us
                and existing_cn
                and existing_us.api_token != existing_cn.api_token
            ):
                existing_cn.api_token = shared_token
            if (
                existing_hk
                and existing_hk.api_token != shared_token
            ):
                existing_hk.api_token = shared_token

            # 新规则：统一人民币钱包
            total_cny = Decimal(str(settings.total_starting_capital_cny))
            wallet_cash = total_cny.quantize(Decimal("0.01"))

            wallet_id = f"{agent_data['id']}-wallet"
            existing_wallet = (
                await db.execute(select(Wallet).where(Wallet.id == wallet_id))
            ).scalar_one_or_none()
            if not existing_wallet:
                db.add(
                    Wallet(
                        id=wallet_id,
                        agent_id=agent_data["id"],
                        currency="CNY",
                        initial_cash=wallet_cash,
                        cash=wallet_cash,
                    )
                )

            if not existing_us:
                us_account = Account(
                    id=us_id,
                    agent_id=agent_data["id"],
                    market="us",
                    currency="CNY",
                    initial_cash=Decimal("0.00"),
                    cash=wallet_cash,
                    api_token=shared_token,
                )
                db.add(us_account)

            if not existing_cn:
                cn_account = Account(
                    id=cn_id,
                    agent_id=agent_data["id"],
                    market="cn",
                    currency="CNY",
                    initial_cash=Decimal("0.00"),
                    cash=wallet_cash,
                    api_token=shared_token,
                )
                db.add(cn_account)

            if not existing_hk:
                hk_account = Account(
                    id=hk_id,
                    agent_id=agent_data["id"],
                    market="hk",
                    currency="CNY",
                    initial_cash=Decimal("0.00"),
                    cash=wallet_cash,
                    api_token=shared_token,
                )
                db.add(hk_account)

        await db.commit()
        print("Wallet/Account base records ensured. No official agents were seeded.")

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
