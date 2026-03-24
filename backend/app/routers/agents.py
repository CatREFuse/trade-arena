from __future__ import annotations

import hashlib
import io
import re
import secrets
import zipfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_account
from app.config import settings
from app.database import get_db
from app.models import Agent, Account, Season, Snapshot
from app.schemas import (
    AgentEmailCodeRequest,
    AgentEmailCodeResponse,
    AgentOut,
    AgentRegisterRequest,
    AgentRegisterResponse,
    ChartPointOut,
)
from app.services.email_verification import (
    EMAIL_CODE_COOLDOWN,
    EMAIL_CODE_TTL,
    cooldown_cache_key,
    issue_email_code,
    normalize_email,
    send_email_code,
    verify_email_code,
)

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _package_skill_archive(
    skill_dir: Path,
    archive_name: str,
    files: list[str] | None = None,
) -> io.BytesIO:
    """
    Package a skill directory into a zip archive.

    Args:
        skill_dir: Root directory of the skill package
        archive_name: Name for the output archive (without extension)
        files: Optional list of specific files to include. If None, includes all files recursively.

    Returns:
        BytesIO buffer containing the zip archive
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if files is not None:
            # Only include specific files
            for f in files:
                fp = skill_dir / f
                if fp.exists():
                    zf.write(fp, f)
        else:
            # Include all files recursively
            for fp in skill_dir.rglob("*"):
                if fp.is_file():
                    relative_path = fp.relative_to(skill_dir)
                    zf.write(fp, str(relative_path))
    buf.seek(0)
    return buf


@router.get("/me")
async def get_me(
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """用 Token 查看自己的 agent 信息和账户"""
    agent_result = await db.execute(select(Agent).where(Agent.id == account.agent_id))
    agent = agent_result.scalar_one()
    accounts_result = await db.execute(
        select(Account).where(Account.agent_id == account.agent_id)
    )
    accs = accounts_result.scalars().all()
    return {
        "agent_id": agent.id,
        "name": agent.name,
        "avatar": agent.avatar,
        "model": agent.model,
        "accounts": {
            a.market: {"id": a.id, "cash": str(a.cash), "currency": a.currency}
            for a in accs
        },
    }


@router.get("/skill/download")
async def download_skill():
    """下载可直接安装的 trade-race skill 包"""
    skill_dir = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "agents"
        / "trade-arena-skill"
    )
    buf = _package_skill_archive(
        skill_dir, "trade-arena-skill", ["SKILL.md", "config.example.json"]
    )
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=trade-arena-skill.zip"},
    )


@router.get("/skill/hosted")
async def download_hosted_skill():
    """下载托管的 cocoloop-trade-arena skill 包"""
    skill_dir = (
        Path(__file__).resolve().parent.parent.parent.parent / "cocoloop-trade-arena"
    )
    if not skill_dir.exists():
        raise HTTPException(
            404,
            detail={
                "error": "SKILL_NOT_FOUND",
                "message": "Hosted skill package not found",
            },
        )

    buf = _package_skill_archive(skill_dir, "cocoloop-trade-arena")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=cocoloop-trade-arena.zip"
        },
    )


@router.get("/skill/hosted/{file_path:path}")
async def get_hosted_skill_file(file_path: str):
    """直接访问托管 skill 包中的单个文件（如 SKILL.md、config.json 等）"""
    from fastapi.responses import FileResponse, PlainTextResponse

    skill_dir = (
        Path(__file__).resolve().parent.parent.parent.parent / "cocoloop-trade-arena"
    )
    if not skill_dir.exists():
        raise HTTPException(
            404,
            detail={
                "error": "SKILL_NOT_FOUND",
                "message": "Hosted skill package not found",
            },
        )

    # 安全检查：防止目录遍历攻击
    requested_path = (skill_dir / file_path).resolve()
    if not str(requested_path).startswith(str(skill_dir.resolve())):
        raise HTTPException(403, detail={"error": "FORBIDDEN", "message": "Access denied"})

    if not requested_path.exists() or not requested_path.is_file():
        raise HTTPException(
            404,
            detail={
                "error": "FILE_NOT_FOUND",
                "message": f"File '{file_path}' not found in skill package",
            },
        )

    # 根据文件类型返回不同响应
    suffix = requested_path.suffix.lower()
    if suffix in ['.md', '.json', '.py', '.txt']:
        # 文本文件直接返回内容
        content = requested_path.read_text(encoding='utf-8')
        media_type = {
            '.md': 'text/markdown; charset=utf-8',
            '.json': 'application/json',
            '.py': 'text/x-python; charset=utf-8',
            '.txt': 'text/plain; charset=utf-8',
        }.get(suffix, 'text/plain; charset=utf-8')
        return PlainTextResponse(content, media_type=media_type)
    else:
        # 二进制文件返回文件下载
        return FileResponse(requested_path)


@router.get("/template/download")
async def download_template():
    raise HTTPException(
        410,
        detail={
            "error": "TEMPLATE_RETIRED",
            "message": "交易模板已下线，请改用 skill 并由选手自行配置 Agent 工作空间",
        },
    )


@router.get("/", response_model=list[AgentOut])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).order_by(Agent.created_at))
    return [
        AgentOut(
            id=a.id,
            name=a.name,
            avatar=a.avatar,
            model=a.model,
            camp=a.camp,
            style=a.style,
            framework=a.framework,
            created_at=a.created_at,
        )
        for a in result.scalars().all()
    ]


@router.post("/register/send-code", response_model=AgentEmailCodeResponse)
async def send_register_email_code(
    req: AgentEmailCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    email = normalize_email(req.email)
    existing = await db.execute(select(Agent).where(Agent.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            409, detail={"error": "EMAIL_ALREADY_USED", "message": "该邮箱已注册过选手"}
        )

    redis = request.app.state.redis
    cooldown = await redis.get(cooldown_cache_key(email))
    if cooldown:
        raise HTTPException(
            429,
            detail={
                "error": "CODE_RATE_LIMITED",
                "message": "验证码发送过于频繁，请稍后再试",
            },
        )

    code = await issue_email_code(redis, email)
    try:
        delivery, dev_code = await send_email_code(email, code)
    except RuntimeError as exc:
        raise HTTPException(
            503,
            detail={"error": "EMAIL_DELIVERY_UNAVAILABLE", "message": str(exc)},
        ) from exc

    return AgentEmailCodeResponse(
        email=email,
        expires_in=EMAIL_CODE_TTL,
        cooldown_in=EMAIL_CODE_COOLDOWN,
        delivery=delivery,
        dev_code=dev_code,
    )


@router.post("/register", response_model=AgentRegisterResponse)
async def register_agent(
    req: AgentRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    email = normalize_email(req.email)

    # 1. 生成 agent_id
    agent_id = _generate_agent_id(req.name)

    # 2. 确保 agent_id 唯一
    existing = await db.execute(select(Agent).where(Agent.id == agent_id))
    if existing.scalar_one_or_none():
        for suffix in range(2, 100):
            candidate = f"{agent_id}-{suffix}"
            check = await db.execute(select(Agent).where(Agent.id == candidate))
            if not check.scalar_one_or_none():
                agent_id = candidate
                break
        else:
            raise HTTPException(
                409,
                detail={
                    "error": "AGENT_ID_CONFLICT",
                    "message": "无法生成唯一 ID，请更换名称",
                },
            )

    # 3. 检查名称唯一
    name_check = await db.execute(select(Agent).where(Agent.name == req.name.strip()))
    if name_check.scalar_one_or_none():
        raise HTTPException(
            409, detail={"error": "AGENT_NAME_CONFLICT", "message": "该名称已被使用"}
        )

    email_check = await db.execute(select(Agent).where(Agent.email == email))
    if email_check.scalar_one_or_none():
        raise HTTPException(
            409, detail={"error": "EMAIL_ALREADY_USED", "message": "该邮箱已注册过选手"}
        )

    redis = request.app.state.redis
    if not await verify_email_code(redis, email, req.verification_code):
        raise HTTPException(
            400,
            detail={
                "error": "INVALID_VERIFICATION_CODE",
                "message": "邮箱验证码无效或已过期",
            },
        )

    # 4. 获取活跃赛季
    season_result = await db.execute(
        select(Season)
        .where(Season.status == "active")
        .order_by(Season.start_date.desc())
    )
    season = season_result.scalar_one_or_none()
    if not season:
        raise HTTPException(
            500, detail={"error": "NO_ACTIVE_SEASON", "message": "当前没有活跃赛季"}
        )

    # 5. 创建 Agent
    agent = Agent(
        id=agent_id,
        name=req.name.strip(),
        email=email,
        email_verified_at=datetime.utcnow(),
        avatar=req.avatar.strip(),
        model=req.model.strip(),
        camp="community",
        style=req.style.strip(),
        framework=req.framework.strip(),
    )
    db.add(agent)
    await db.flush()

    # 6. 创建两个账户（共用一个 token）
    # 新规则：总资金 100万人民币，按汇率兑换成美元，剩余为人民币
    total_cny = Decimal(str(settings.total_starting_capital_cny))
    exchange_rate = Decimal(str(settings.exchange_rate))
    usd_amount = (total_cny / exchange_rate).quantize(Decimal("0.01"))
    cny_remaining = total_cny - (usd_amount * exchange_rate)

    api_token = secrets.token_hex(32)
    us_account = Account(
        id=f"{agent_id}-us",
        season_id=season.id,
        agent_id=agent_id,
        market="us",
        currency="USD",
        initial_cash=usd_amount,
        cash=usd_amount,
        api_token=api_token,
    )
    db.add(us_account)

    cn_account = Account(
        id=f"{agent_id}-cn",
        season_id=season.id,
        agent_id=agent_id,
        market="cn",
        currency="CNY",
        initial_cash=cny_remaining.quantize(Decimal("0.01")),
        cash=cny_remaining.quantize(Decimal("0.01")),
        api_token=api_token,
    )
    db.add(cn_account)

    await db.commit()
    await db.refresh(agent)

    return AgentRegisterResponse(
        agent=AgentOut(
            id=agent.id,
            name=agent.name,
            avatar=agent.avatar,
            model=agent.model,
            camp=agent.camp,
            style=agent.style,
            framework=agent.framework,
            created_at=agent.created_at,
        ),
        token=api_token,
    )


def _generate_agent_id(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]", "", name.lower())
    if not slug:
        slug = "agent-" + hashlib.md5(name.encode()).hexdigest()[:6]
    return slug[:20]


@router.get("/{agent_id}/chart")
async def get_agent_chart(
    agent_id: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """获取 Agent 资产历史曲线数据"""
    from datetime import date, timedelta
    from sqlalchemy import func

    # 获取 Agent 的所有账户
    result = await db.execute(select(Account).where(Account.agent_id == agent_id))
    accounts = result.scalars().all()

    if not accounts:
        raise HTTPException(404, detail="Agent not found")

    account_ids = [a.id for a in accounts]
    start_date = date.today() - timedelta(days=days)

    # 查询每个日期的总资产（所有账户加总）
    result = await db.execute(
        select(Snapshot.date, func.sum(Snapshot.total_asset).label("total"))
        .where(Snapshot.account_id.in_(account_ids), Snapshot.date >= start_date)
        .group_by(Snapshot.date)
        .order_by(Snapshot.date)
    )

    rows = result.all()

    # 转换为返回格式
    chart_data = [
        {"date": row.date.isoformat(), "value": float(row.total or 0)} for row in rows
    ]

    # 如果没有数据，返回空数组
    return chart_data


@router.get("/{agent_id}/accounts")
async def get_agent_accounts(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取 Agent 的美股和A股账户 ID"""
    # 先确认 agent 存在
    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    if not agent_result.scalar_one_or_none():
        raise HTTPException(
            404, detail={"error": "AGENT_NOT_FOUND", "message": "Agent 不存在"}
        )

    # 查询该 agent 的所有账户
    accounts_result = await db.execute(
        select(Account).where(Account.agent_id == agent_id)
    )
    accounts = accounts_result.scalars().all()

    # 提取 us 和 cn 账户 ID
    us_account_id = None
    cn_account_id = None
    for acc in accounts:
        if acc.market == "us":
            us_account_id = acc.id
        elif acc.market == "cn":
            cn_account_id = acc.id

    return {"us": us_account_id, "cn": cn_account_id}


async def record_snapshot(
    account_id: str,
    total_asset: Decimal,
    cash: Decimal,
    position_value: Decimal,
    db: AsyncSession,
):
    """记录账户资产快照（在交易后调用）"""
    from datetime import date
    from sqlalchemy.dialects.postgresql import insert

    today = date.today()

    # 先查询今天是否已有记录
    existing = await db.execute(
        select(Snapshot).where(
            Snapshot.account_id == account_id, Snapshot.date == today
        )
    )
    existing = existing.scalar_one_or_none()

    if existing:
        # 更新现有记录
        existing.total_asset = total_asset
        existing.cash = cash
        existing.position_value = position_value
        existing.trade_count = existing.trade_count + 1
    else:
        # 插入新记录
        snapshot = Snapshot(
            account_id=account_id,
            date=today,
            total_asset=total_asset,
            cash=cash,
            position_value=position_value,
            trade_count=1,
        )
        db.add(snapshot)

    await db.flush()
