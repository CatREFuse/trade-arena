from __future__ import annotations

import hashlib
import io
import logging
import re
import secrets
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_account
from app.config import settings
from app.database import get_db
from app.models import Agent, Account, AgentEquityPoint, Position, Snapshot, Wallet
from app.schemas import (
    AgentMarketPortfolioOut,
    AgentMeOut,
    AgentPortfolioSummaryOut,
    AgentEquityCurveOut,
    AgentEmailCodeRequest,
    AgentOut,
    AgentRegisterRequest,
    AgentRegisterResponse,
    ChartPointOut,
    PublicPositionOut,
    SkillVersionOut,
)
from app.services.fx import FXService
from app.services.market_data import MarketDataService
from app.services.email_verification import (
    normalize_email,
)

router = APIRouter(prefix="/api/agents", tags=["agents"])
logger = logging.getLogger(__name__)


def _normalize_forwarded_header(value: str | None) -> str:
    if not value:
        return ""
    return value.split(",")[0].strip()


def _is_local_host(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.split(":", 1)[0].strip().strip("[]").lower()
    return normalized in {"localhost", "127.0.0.1", "::1"}


def _build_public_origin(request: Request) -> str:
    forwarded_proto = _normalize_forwarded_header(request.headers.get("x-forwarded-proto"))
    forwarded_host = _normalize_forwarded_header(request.headers.get("x-forwarded-host"))
    host = forwarded_host or request.headers.get("host") or request.url.netloc
    scheme = forwarded_proto or request.url.scheme or "https"

    if scheme == "http" and host and not _is_local_host(host):
        scheme = "https"

    if host:
        return f"{scheme}://{host}".rstrip("/")

    return str(request.base_url).rstrip("/")


def _hosted_skill_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent / "cocoloop-trade-arena"


def _read_skill_version(skill_md_path: Path) -> str:
    content = skill_md_path.read_text(encoding="utf-8")
    front_matter_match = re.search(r"\A---\s*\n(?P<meta>.*?)\n---\s*\n", content, re.DOTALL)
    if not front_matter_match:
        raise ValueError("SKILL.md front matter is missing")
    meta = front_matter_match.group("meta")
    version_match = re.search(
        r"""(?m)^version:\s*(?:"(?P<dq>[^"]+)"|'(?P<sq>[^']+)'|(?P<raw>[^\s#]+))\s*$""",
        meta,
    )
    if not version_match:
        raise ValueError("Skill version is missing in front matter")
    return (version_match.group("dq") or version_match.group("sq") or version_match.group("raw")).strip()


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


async def _build_agent_portfolio_summary_payload(
    agent_id: str,
    request: Request,
    db: AsyncSession,
) -> AgentPortfolioSummaryOut:
    accounts_result = await db.execute(select(Account).where(Account.agent_id == agent_id))
    accounts = accounts_result.scalars().all()
    account_by_market = {account.market: account for account in accounts}

    wallet_result = await db.execute(
        select(Wallet)
        .where(Wallet.agent_id == agent_id)
        .order_by(Wallet.updated_at.desc(), Wallet.created_at.desc())
        .limit(1)
    )
    wallet = wallet_result.scalar_one_or_none()
    wallet_cash_cny = wallet.cash if wallet is not None else Decimal("0")

    account_ids = [account.id for account in accounts]
    positions: list[Position] = []
    if account_ids:
        positions_result = await db.execute(select(Position).where(Position.account_id.in_(account_ids)))
        positions = positions_result.scalars().all()

    redis = request.app.state.redis
    fx_service = getattr(request.app.state, "fx_service", None) or FXService(redis)
    market_svc = getattr(request.app.state, "market_data_service", None) or MarketDataService(redis)

    quote_map = await market_svc.get_quotes_batch([pos.ticker for pos in positions]) if positions else {}
    usd_cny, _, _ = await fx_service.get_rate_to_cny("us")
    hkd_cny, _, _ = await fx_service.get_rate_to_cny("hk")
    rate_map = {
        "cn": Decimal("1"),
        "us": Decimal(str(usd_cny)),
        "hk": Decimal(str(hkd_cny)),
    }

    market_positions: dict[str, list[PublicPositionOut]] = {"us": [], "cn": [], "hk": []}
    market_position_values: dict[str, Decimal] = {"us": Decimal("0"), "cn": Decimal("0"), "hk": Decimal("0")}
    account_by_id = {account.id: account for account in accounts}

    for position in positions:
        account = account_by_id.get(position.account_id)
        if account is None:
            continue
        market = account.market
        fx = rate_map.get(market, Decimal("1"))
        quote = quote_map.get(position.ticker)
        current_price_local = quote.price if quote is not None else position.avg_cost
        current_price_cny = current_price_local * fx
        avg_cost_cny = position.avg_cost * fx
        pnl_cny = (current_price_local - position.avg_cost) * position.shares * fx
        market_value_cny = current_price_cny * position.shares

        market_positions[market].append(
            PublicPositionOut(
                ticker=position.ticker,
                shares=position.shares,
                avg_cost_cny=avg_cost_cny,
                current_price_cny=current_price_cny,
                pnl_cny=pnl_cny,
                market_value_cny=market_value_cny,
            )
        )
        market_position_values[market] = market_position_values[market] + market_value_cny

    for market in market_positions:
        market_positions[market].sort(
            key=lambda item: item.market_value_cny,
            reverse=True,
        )

    markets: list[AgentMarketPortfolioOut] = []
    for market in ("us", "cn", "hk"):
        market_account = account_by_market.get(market)
        positions_out = market_positions[market]
        markets.append(
            AgentMarketPortfolioOut(
                market=market,
                account_id=(market_account.id if market_account is not None else None),
                holdings_count=len(positions_out),
                position_value_cny=market_position_values[market],
                positions=positions_out,
            )
        )

    total_asset_cny = wallet_cash_cny + sum(market_position_values.values())
    return AgentPortfolioSummaryOut(
        agent_id=agent_id,
        wallet_cash_cny=wallet_cash_cny,
        total_asset_cny=total_asset_cny,
        markets=markets,
        updated_at=datetime.now(timezone.utc),
    )


@router.get("/me", response_model=AgentMeOut)
async def get_me(
    request: Request,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """用 Token 查看自己的 agent 信息和账户"""
    agent_result = await db.execute(
        select(Agent).where(Agent.id == account.agent_id, Agent.is_deleted.is_(False))
    )
    agent = agent_result.scalar_one()
    summary = await _build_agent_portfolio_summary_payload(
        agent_id=account.agent_id,
        request=request,
        db=db,
    )
    account_refs = {
        market_summary.market: {"id": market_summary.account_id}
        for market_summary in summary.markets
        if market_summary.account_id is not None
    }
    return AgentMeOut(
        agent_id=agent.id,
        name=agent.name,
        avatar=agent.avatar,
        model=agent.model,
        wallet_cash_cny=summary.wallet_cash_cny,
        total_asset_cny=summary.total_asset_cny,
        accounts=account_refs,
        market_holdings=summary.markets,
        updated_at=summary.updated_at,
    )


@router.delete("/me/regression")
async def cleanup_regression_agent(
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    """逻辑删除回归测试注册的临时 Agent 数据。"""
    agent_result = await db.execute(
        select(Agent).where(Agent.id == account.agent_id, Agent.is_deleted.is_(False))
    )
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "AGENT_NOT_FOUND", "message": "Agent 不存在"},
        )

    name = (agent.name or "").strip().lower()
    email = (agent.email or "").strip().lower()
    is_regression_agent = name.startswith("regress-") or email.startswith("regress.")
    if not is_regression_agent:
        raise HTTPException(
            status_code=403,
            detail={"error": "FORBIDDEN", "message": "仅允许清理回归测试选手"},
        )

    agent.is_deleted = True
    agent.deleted_at = datetime.utcnow()
    agent.deleted_by = "api:/api/agents/me/regression"
    agent.delete_reason = "regression cleanup"
    await db.commit()
    return {"status": "deleted", "agent_id": agent.id}


@router.get("/skill/download")
async def download_skill():
    """下载 cocoloop-trade-arena skill 包（与 /skill/hosted 相同）"""
    skill_dir = _hosted_skill_dir()
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


@router.get("/skill/hosted")
async def download_hosted_skill():
    """下载托管的 cocoloop-trade-arena skill 包"""
    skill_dir = _hosted_skill_dir()
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


@router.get("/skill/version", response_model=SkillVersionOut)
async def get_hosted_skill_version(request: Request):
    """返回当前托管 skill 的版本和下载链接"""
    skill_dir = _hosted_skill_dir()
    if not skill_dir.exists():
        raise HTTPException(
            404,
            detail={
                "error": "SKILL_NOT_FOUND",
                "message": "Hosted skill package not found",
            },
        )

    skill_md_path = skill_dir / "SKILL.md"
    if not skill_md_path.exists():
        raise HTTPException(
            404,
            detail={
                "error": "SKILL_METADATA_NOT_FOUND",
                "message": "SKILL.md not found in hosted skill package",
            },
        )

    try:
        version = _read_skill_version(skill_md_path)
    except ValueError as exc:
        raise HTTPException(
            500,
            detail={
                "error": "SKILL_METADATA_INVALID",
                "message": str(exc),
            },
        )

    return SkillVersionOut(
        version=version,
        hosted_url=f"{_build_public_origin(request)}/api/agents/skill/hosted",
    )


@router.get("/skill/hosted/{file_path:path}")
async def get_hosted_skill_file(file_path: str):
    """直接访问托管 skill 包中的单个文件（如 SKILL.md、config.json 等）"""
    from fastapi.responses import FileResponse, PlainTextResponse

    skill_dir = _hosted_skill_dir()
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


async def _query_agents(
    request: Request,
    db: AsyncSession,
) -> list[AgentOut]:
    try:
        result = await db.execute(
            select(Agent).where(Agent.is_deleted.is_(False)).order_by(Agent.created_at)
        )
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
    except SQLAlchemyError as e:
        logger.error(f"[{request.method} {request.url.path}] DB_ERROR: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "DATABASE_UNAVAILABLE",
                "message": "数据库暂时不可用，请稍后重试",
            },
        )
    except Exception as e:
        logger.error(f"[{request.method} {request.url.path}] UNEXPECTED_ERROR: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "SERVICE_UNAVAILABLE",
                "message": "服务暂时不可用，请稍后重试",
            },
        )


@router.get("", response_model=list[AgentOut], include_in_schema=False)
async def list_agents_without_trailing_slash(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """获取所有 Agent 列表（无尾斜杠路径，避免 307 重定向）"""
    return await _query_agents(request=request, db=db)


@router.get("/", response_model=list[AgentOut])
async def list_agents(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """获取所有 Agent 列表"""
    return await _query_agents(request=request, db=db)


@router.post("/register/send-code")
async def send_register_email_code(
    req: AgentEmailCodeRequest,
):
    email = normalize_email(req.email)
    raise HTTPException(
        410,
        detail={
            "error": "EMAIL_VERIFICATION_DISABLED",
            "message": f"邮箱验证码流程已下线，请直接用邮箱 {email} 提交注册",
        },
    )


@router.post("/register", response_model=AgentRegisterResponse)
async def register_agent(
    req: AgentRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """注册新 Agent，创建 US/CN/HK 三市场账户与统一人民币钱包"""
    email = normalize_email(req.email)
    log_prefix = f"[{request.method} {request.url.path}]"

    try:
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
                logger.warning(f"{log_prefix} AGENT_ID_CONFLICT: name={req.name}")
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
            logger.warning(f"{log_prefix} AGENT_NAME_CONFLICT: name={req.name}")
            raise HTTPException(
                409, detail={"error": "AGENT_NAME_CONFLICT", "message": "该名称已被使用"}
            )

        email_check = await db.execute(select(Agent).where(Agent.email == email))
        if email_check.scalar_one_or_none():
            logger.warning(f"{log_prefix} EMAIL_ALREADY_USED: email={email}")
            raise HTTPException(
                409, detail={"error": "EMAIL_ALREADY_USED", "message": "该邮箱已注册过选手"}
            )

        # 4. 创建 Agent
        agent = Agent(
            id=agent_id,
            name=req.name.strip(),
            email=email,
            email_verified_at=None,
            avatar=req.avatar.strip(),
            model=req.model.strip(),
            camp="community",
            style=req.style.strip(),
            framework=req.framework.strip(),
        )
        db.add(agent)
        await db.flush()

        # 6. 创建账户与统一人民币钱包（共用一个 token）
        total_cny = Decimal(str(settings.total_starting_capital_cny))
        initial_wallet_cash = total_cny.quantize(Decimal("0.01"))

        api_token = secrets.token_hex(32)
        us_account = Account(
            id=f"{agent_id}-us",
            agent_id=agent_id,
            market="us",
            currency="CNY",
            initial_cash=Decimal("0.00"),
            cash=initial_wallet_cash,
            api_token=api_token,
        )
        db.add(us_account)

        cn_account = Account(
            id=f"{agent_id}-cn",
            agent_id=agent_id,
            market="cn",
            currency="CNY",
            initial_cash=Decimal("0.00"),
            cash=initial_wallet_cash,
            api_token=api_token,
        )
        db.add(cn_account)

        hk_account = Account(
            id=f"{agent_id}-hk",
            agent_id=agent_id,
            market="hk",
            currency="CNY",
            initial_cash=Decimal("0.00"),
            cash=initial_wallet_cash,
            api_token=api_token,
        )
        db.add(hk_account)

        wallet = Wallet(
            id=f"{agent_id}-wallet",
            agent_id=agent_id,
            currency="CNY",
            initial_cash=initial_wallet_cash,
            cash=initial_wallet_cash,
        )
        db.add(wallet)

        await db.commit()
        await db.refresh(agent)

        logger.info(f"{log_prefix} AGENT_REGISTERED: agent_id={agent_id}, email={email}")
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
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"{log_prefix} REGISTRATION_DB_ERROR: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "REGISTRATION_UNAVAILABLE",
                "message": "注册服务暂时不可用，请稍后重试",
            },
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"{log_prefix} REGISTRATION_UNEXPECTED_ERROR: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "REGISTRATION_FAILED",
                "message": "注册失败，请稍后重试",
            },
        )


def _generate_agent_id(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]", "", name.lower())
    if not slug:
        slug = "agent-" + hashlib.md5(name.encode()).hexdigest()[:6]
    return slug[:20]


_CURVE_CHART_TYPE_DEFAULT_SPAN: dict[str, str] = {
    "intraday": "1d",
    "swing": "7d",
    "trend": "30d",
    "long": "max",
}

_CURVE_SPAN_DAYS: dict[str, int | None] = {
    "1d": 1,
    "3d": 3,
    "7d": 7,
    "30d": 30,
    "max": None,
}

_CURVE_INTERVAL_MINUTES: dict[str, int] = {
    "5m": 5,
    "15m": 15,
    "1h": 60,
    "1d": 1440,
}


def _floor_to_five_minutes(ts: datetime) -> datetime:
    return ts.replace(minute=(ts.minute // 5) * 5, second=0, microsecond=0)


def _resolve_curve_span(
    span: str | None,
    chart_type: str | None,
) -> str:
    if span and span in _CURVE_SPAN_DAYS:
        return span
    if chart_type and chart_type in _CURVE_CHART_TYPE_DEFAULT_SPAN:
        return _CURVE_CHART_TYPE_DEFAULT_SPAN[chart_type]
    return "30d"


def _resolve_curve_interval(span: str, interval: str) -> str:
    if interval in _CURVE_INTERVAL_MINUTES:
        return interval
    if span == "1d":
        return "5m"
    if span in {"3d", "7d"}:
        return "15m"
    if span == "30d":
        return "1h"
    return "1d"


def _resample_curve_rows(
    rows: list[tuple[datetime, Decimal]],
    interval_minutes: int,
) -> list[tuple[datetime, Decimal]]:
    if not rows or interval_minutes <= 5:
        return rows

    bucket_seconds = interval_minutes * 60
    sampled: dict[int, tuple[datetime, Decimal]] = {}
    for point_time, equity in rows:
        bucket_key = int(point_time.timestamp()) // bucket_seconds
        sampled[bucket_key] = (point_time, equity)
    return [sampled[key] for key in sorted(sampled.keys())]


def _downsample_curve_rows(
    rows: list[tuple[datetime, Decimal]],
    max_points: int = 900,
) -> list[tuple[datetime, Decimal]]:
    if len(rows) <= max_points:
        return rows
    if max_points <= 1:
        return [rows[-1]]
    sampled: list[tuple[datetime, Decimal]] = []
    last_index = len(rows) - 1
    for i in range(max_points):
        idx = round(i * last_index / (max_points - 1))
        sampled.append(rows[idx])
    return sampled


async def _build_agent_curve_payload(
    *,
    agent_id: str,
    db: AsyncSession,
    span: str,
    interval: str,
) -> AgentEquityCurveOut:
    interval_minutes = _CURVE_INTERVAL_MINUTES[interval]
    end_time = _floor_to_five_minutes(datetime.utcnow())
    span_days = _CURVE_SPAN_DAYS[span]
    start_time = end_time - timedelta(days=span_days) if span_days is not None else None

    query = (
        select(AgentEquityPoint.point_time, AgentEquityPoint.equity_cny)
        .where(AgentEquityPoint.agent_id == agent_id)
        .order_by(AgentEquityPoint.point_time)
    )
    if start_time is not None:
        query = query.where(AgentEquityPoint.point_time >= start_time)

    rows_result = await db.execute(query)
    rows = [(point_time, equity_cny) for point_time, equity_cny in rows_result.all()]

    wallet_result = await db.execute(
        select(Wallet)
        .where(Wallet.agent_id == agent_id)
        .order_by(Wallet.updated_at.desc(), Wallet.created_at.desc())
        .limit(1)
    )
    wallet = wallet_result.scalar_one_or_none()
    initial_value = wallet.initial_cash if wallet is not None else Decimal(str(settings.total_starting_capital_cny))

    if not rows:
        synthetic_start = start_time or (end_time - timedelta(days=30))
        points = [
            ChartPointOut(date=synthetic_start.isoformat(), value=float(initial_value)),
            ChartPointOut(date=end_time.isoformat(), value=float(initial_value)),
        ]
        return AgentEquityCurveOut(span=span, interval=interval, points=points)

    sampled_rows = _resample_curve_rows(rows, interval_minutes)
    sampled_rows = _downsample_curve_rows(sampled_rows)
    if len(sampled_rows) == 1:
        only_time, only_value = sampled_rows[0]
        start_anchor = start_time or (only_time - timedelta(minutes=5))
        if start_anchor >= only_time:
            start_anchor = only_time - timedelta(minutes=5)
        sampled_rows = [(start_anchor, only_value), (only_time, only_value)]
    points = [
        ChartPointOut(date=point_time.isoformat(), value=float(equity_cny))
        for point_time, equity_cny in sampled_rows
    ]
    return AgentEquityCurveOut(span=span, interval=interval, points=points)


@router.get("/{agent_id}/equity-curve", response_model=AgentEquityCurveOut)
async def get_agent_equity_curve(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    span: str | None = None,
    chart_type: Literal["intraday", "swing", "trend", "long"] | None = None,
    interval: Literal["auto", "5m", "15m", "1h", "1d"] = "auto",
):
    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.is_deleted.is_(False))
    )
    if not agent_result.scalar_one_or_none():
        raise HTTPException(404, detail="Agent not found")

    resolved_span = _resolve_curve_span(span, chart_type)
    resolved_interval = _resolve_curve_interval(resolved_span, interval)
    return await _build_agent_curve_payload(
        agent_id=agent_id,
        db=db,
        span=resolved_span,
        interval=resolved_interval,
    )


@router.get("/{agent_id}/chart")
async def get_agent_chart(
    agent_id: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """兼容旧接口：返回资产曲线点数组。"""
    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.is_deleted.is_(False))
    )
    if not agent_result.scalar_one_or_none():
        raise HTTPException(404, detail="Agent not found")

    if days <= 1:
        span = "1d"
    elif days <= 3:
        span = "3d"
    elif days <= 7:
        span = "7d"
    elif days <= 30:
        span = "30d"
    else:
        span = "max"
    interval = _resolve_curve_interval(span, "auto")
    curve = await _build_agent_curve_payload(
        agent_id=agent_id,
        db=db,
        span=span,
        interval=interval,
    )
    return curve.points


@router.get("/{agent_id}/accounts")
async def get_agent_accounts(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取 Agent 的 US/CN/HK 账户 ID"""
    # 先确认 agent 存在
    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.is_deleted.is_(False))
    )
    if not agent_result.scalar_one_or_none():
        raise HTTPException(
            404, detail={"error": "AGENT_NOT_FOUND", "message": "Agent 不存在"}
        )

    # 查询该 agent 的所有账户
    accounts_result = await db.execute(
        select(Account).where(Account.agent_id == agent_id)
    )
    accounts = accounts_result.scalars().all()

    # 提取 us / cn / hk 账户 ID
    us_account_id = None
    cn_account_id = None
    hk_account_id = None
    for acc in accounts:
        if acc.market == "us":
            us_account_id = acc.id
        elif acc.market == "cn":
            cn_account_id = acc.id
        elif acc.market == "hk":
            hk_account_id = acc.id

    return {
        "us": {"id": us_account_id} if us_account_id else None,
        "cn": {"id": cn_account_id} if cn_account_id else None,
        "hk": {"id": hk_account_id} if hk_account_id else None,
    }


@router.get("/{agent_id}/portfolio-summary", response_model=AgentPortfolioSummaryOut)
async def get_agent_portfolio_summary(
    agent_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """公开返回 Agent 分市场持仓汇总（人民币口径）。"""
    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.is_deleted.is_(False))
    )
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(
            404,
            detail={"error": "AGENT_NOT_FOUND", "message": "Agent 不存在"},
        )

    return await _build_agent_portfolio_summary_payload(
        agent_id=agent_id,
        request=request,
        db=db,
    )


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
