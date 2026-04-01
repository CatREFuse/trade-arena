"""开发用 Mock 数据开关"""

from __future__ import annotations

import logging
import random
import secrets
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Agent, Account, Trade, Position, Season, Snapshot, Wallet

router = APIRouter(prefix="/api/dev", tags=["dev"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def dev_status(db: AsyncSession = Depends(get_db)):
    """检查当前是否有数据"""
    try:
        from sqlalchemy import func

        agent_count = (await db.execute(select(func.count()).select_from(Agent))).scalar()
        trade_count = (await db.execute(select(func.count()).select_from(Trade))).scalar()
        return {"has_data": agent_count > 0, "agents": agent_count, "trades": trade_count}
    except SQLAlchemyError as e:
        logger.error(f"[GET /api/dev/status] DB_ERROR: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "DATABASE_UNAVAILABLE",
                "message": "数据库暂时不可用",
            },
        )
    except Exception as e:
        logger.error(f"[GET /api/dev/status] UNEXPECTED_ERROR: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "SERVICE_UNAVAILABLE",
                "message": "服务暂时不可用",
            },
        )


MOCK_AGENTS = [
    {
        "id": "community-alpha",
        "name": "南山一号",
        "avatar": "🛰️",
        "model": "gpt-5.4",
        "camp": "community",
        "style": "事件驱动 + 快速调仓",
        "framework": "custom",
    },
    {
        "id": "community-bravo",
        "name": "港口风帆",
        "avatar": "⛵",
        "model": "claude-sonnet-4",
        "camp": "community",
        "style": "高股息 + 防守轮动",
        "framework": "custom",
    },
    {
        "id": "community-charlie",
        "name": "夜航者",
        "avatar": "🦉",
        "model": "gemini-2.5-pro",
        "camp": "community",
        "style": "盘后复盘 + 开盘执行",
        "framework": "custom",
    },
    {
        "id": "community-delta",
        "name": "薄荷因子",
        "avatar": "🌿",
        "model": "deepseek-v3",
        "camp": "community",
        "style": "多因子量化",
        "framework": "custom",
    },
]

US_TICKERS = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META", "AMD"]
CN_TICKERS = ["600519.SH", "000858.SZ", "300750.SZ", "002594.SZ", "601318.SH"]
HK_TICKERS = ["0700.HK", "9988.HK", "3690.HK", "1810.HK", "1211.HK"]
REASONINGS = [
    "技术面突破关键阻力位，成交量放大确认趋势",
    "基本面强劲，最新财报超预期",
    "估值处于历史低位，安全边际充足",
    "MACD金叉 + RSI超卖区反弹信号",
    "机构资金连续流入，主力建仓迹象明显",
    "量化模型信号：动量因子转正",
    "获利兑现，落袋为安",
    "止损离场，趋势反转信号确认",
    "AI芯片需求超预期，产业链验证增长逻辑",
    "消费复苏信号明确，板块估值修复",
]

RETURN_RANGES = {
    "community-alpha": (1, 12),
    "community-bravo": (-2, 6),
    "community-charlie": (-4, 14),
    "community-delta": (0, 10),
}


@router.post("/mock")
async def enable_mock(db: AsyncSession = Depends(get_db)):
    """生成 mock 数据用于 UI 预览"""
    # 确保赛季存在
    from datetime import date

    season = (
        await db.execute(select(Season).where(Season.id == "2026-Q1"))
    ).scalar_one_or_none()
    if not season:
        db.add(
            Season(
                id="2026-Q1",
                name="第一赛季",
                start_date=date(2026, 3, 18),
                status="active",
            )
        )

    now = datetime.utcnow()

    for agent_data in MOCK_AGENTS:
        # Agent
        existing = (
            await db.execute(select(Agent).where(Agent.id == agent_data["id"]))
        ).scalar_one_or_none()
        if not existing:
            db.add(Agent(**agent_data))
            await db.flush()

        ret_lo, ret_hi = RETURN_RANGES[agent_data["id"]]
        us_ret = random.uniform(ret_lo, ret_hi)
        cn_ret = random.uniform(ret_lo * 0.8, ret_hi * 0.8)
        hk_ret = random.uniform(ret_lo * 0.6, ret_hi * 0.9)

        # 新规则：总资金 100万人民币，统一钱包
        total_cny = Decimal(str(settings.total_starting_capital_cny))
        wallet_initial = total_cny.quantize(Decimal("0.01"))
        blended_return = Decimal(str(round((us_ret + cn_ret + hk_ret) / 3, 2)))
        wallet_cash = Decimal(
            str(round(float(wallet_initial) * (1 + float(blended_return) / 100), 2))
        )
        wallet_id = f"{agent_data['id']}-2026-Q1-wallet"
        wallet = (
            await db.execute(select(Wallet).where(Wallet.id == wallet_id))
        ).scalar_one_or_none()
        if not wallet:
            db.add(
                Wallet(
                    id=wallet_id,
                    season_id="2026-Q1",
                    agent_id=agent_data["id"],
                    currency="CNY",
                    initial_cash=wallet_initial,
                    cash=wallet_cash,
                )
            )
        else:
            wallet.initial_cash = wallet_initial
            wallet.cash = wallet_cash

        # US Account
        us_id = f"{agent_data['id']}-us"
        us_acc = (
            await db.execute(select(Account).where(Account.id == us_id))
        ).scalar_one_or_none()
        if not us_acc:
            db.add(
                Account(
                    id=us_id,
                    season_id="2026-Q1",
                    agent_id=agent_data["id"],
                    market="us",
                    currency="CNY",
                    initial_cash=Decimal("0.00"),
                    cash=wallet_cash,
                    api_token=secrets.token_hex(32),
                )
            )
        else:
            us_acc.cash = wallet_cash

        # CN Account
        cn_id = f"{agent_data['id']}-cn"
        cn_acc = (
            await db.execute(select(Account).where(Account.id == cn_id))
        ).scalar_one_or_none()
        if not cn_acc:
            db.add(
                Account(
                    id=cn_id,
                    season_id="2026-Q1",
                    agent_id=agent_data["id"],
                    market="cn",
                    currency="CNY",
                    initial_cash=Decimal("0.00"),
                    cash=wallet_cash,
                    api_token=secrets.token_hex(32),
                )
            )
        else:
            cn_acc.cash = wallet_cash

        # HK Account
        hk_id = f"{agent_data['id']}-hk"
        hk_acc = (
            await db.execute(select(Account).where(Account.id == hk_id))
        ).scalar_one_or_none()
        if not hk_acc:
            db.add(
                Account(
                    id=hk_id,
                    season_id="2026-Q1",
                    agent_id=agent_data["id"],
                    market="hk",
                    currency="CNY",
                    initial_cash=Decimal("0.00"),
                    cash=wallet_cash,
                    api_token=secrets.token_hex(32),
                )
            )
        else:
            hk_acc.cash = wallet_cash

        # Trades
        for _ in range(random.randint(4, 10)):
            market = random.choices(["us", "cn", "hk"], weights=[0.45, 0.35, 0.20])[0]
            ticker_pool = US_TICKERS if market == "us" else (CN_TICKERS if market == "cn" else HK_TICKERS)
            ticker = random.choice(ticker_pool)
            action = random.choice(["buy", "sell"])
            price = Decimal(str(round(random.uniform(15, 800), 2)))
            shares = Decimal(str(round(random.uniform(10, 500), 1)))
            amount = price * shares
            fee = (amount * Decimal("0.001")).quantize(Decimal("0.01"))
            db.add(
                Trade(
                    account_id=f"{agent_data['id']}-{market}",
                    ticker=ticker,
                    action=action,
                    shares=shares,
                    price=price,
                    amount=amount,
                    fee=fee,
                    fx_pair=("USD/CNY" if market == "us" else ("HKD/CNY" if market == "hk" else "CNY/CNY")),
                    fx_rate=(Decimal("7.2") if market == "us" else (Decimal("0.92") if market == "hk" else Decimal("1"))),
                    amount_cny=(amount * (Decimal("7.2") if market == "us" else (Decimal("0.92") if market == "hk" else Decimal("1")))).quantize(Decimal("0.01")),
                    fee_cny=(fee * (Decimal("7.2") if market == "us" else (Decimal("0.92") if market == "hk" else Decimal("1")))).quantize(Decimal("0.01")),
                    cash_after_cny=wallet_cash,
                    reasoning=random.choice(REASONINGS),
                    created_at=now
                    - timedelta(
                        hours=random.randint(0, 72), minutes=random.randint(0, 59)
                    ),
                )
            )

    await db.commit()

    # 生成历史资产快照（用于图表展示）
    await _generate_mock_snapshots(db)

    return {"status": "mock", "agents": len(MOCK_AGENTS)}


async def _generate_mock_snapshots(db: AsyncSession):
    """为每个账户生成过去 30 天的资产快照"""
    from datetime import date, timedelta
    from sqlalchemy import func

    today = date.today()

    # 获取所有账户和钱包
    result = await db.execute(select(Account))
    accounts = result.scalars().all()
    wallet_result = await db.execute(select(Wallet))
    wallet_by_agent = {wallet.agent_id: wallet for wallet in wallet_result.scalars().all()}

    for acc in accounts:
        wallet = wallet_by_agent.get(acc.agent_id)
        initial = float(wallet.initial_cash if wallet else Decimal(str(settings.total_starting_capital_cny)))
        current = float(wallet.cash if wallet else Decimal(str(settings.total_starting_capital_cny)))

        # 生成 30 天的数据，从初始资金渐变到当前资金
        for i in range(30, -1, -1):
            snapshot_date = today - timedelta(days=i)

            # 计算该日期的资产（使用随机游走模拟）
            progress = (30 - i) / 30  # 0.0 ~ 1.0
            base_value = initial + (current - initial) * progress

            # 添加一些随机波动
            noise = random.uniform(-0.02, 0.02)
            day_value = base_value * (1 + noise)

            # 计算持仓市值（模拟一些持仓）
            position_ratio = random.uniform(0.3, 0.7)  # 30%~70% 持仓
            position_value = day_value * position_ratio
            cash_value = day_value * (1 - position_ratio)

            # 检查是否已存在
            existing = await db.execute(
                select(Snapshot).where(
                    Snapshot.account_id == acc.id, Snapshot.date == snapshot_date
                )
            )
            if not existing.scalar_one_or_none():
                db.add(
                    Snapshot(
                        account_id=acc.id,
                        date=snapshot_date,
                        total_asset=Decimal(str(round(day_value, 2))),
                        cash=Decimal(str(round(cash_value, 2))),
                        position_value=Decimal(str(round(position_value, 2))),
                        trade_count=random.randint(0, 5),
                    )
                )

    await db.commit()


@router.post("/reset")
async def reset_data(db: AsyncSession = Depends(get_db)):
    """清空所有数据"""
    await db.execute(delete(Trade))
    await db.execute(delete(Position))
    await db.execute(delete(Wallet))
    await db.execute(delete(Account))
    await db.execute(delete(Agent))
    await db.commit()
    return {"status": "reset"}
