from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models import Account, Agent, Season


@pytest.mark.asyncio
async def test_register_agent_success_without_email_verification(
    client, db_session_factory
):
    register_response = await client.post(
        "/api/agents/register",
        json={
            "name": "Player One",
            "email": "player@example.com",
            "model": "gpt-5.4",
            "avatar": "🚀",
            "style": "趋势交易 + 风控优先",
            "framework": "custom",
        },
    )

    assert register_response.status_code == 200
    register_payload = register_response.json()
    assert register_payload["agent"]["id"] == "playerone"
    assert len(register_payload["token"]) == 64

    async with db_session_factory() as session:
        result = await session.execute(select(Agent).where(Agent.id == "playerone"))
        agent = result.scalar_one()
        assert agent.email == "player@example.com"
        assert agent.email_verified_at is None


@pytest.mark.asyncio
async def test_register_send_code_endpoint_is_disabled(client):
    response = await client.post(
        "/api/agents/register/send-code",
        json={"email": "wrong-code@example.com"},
    )
    assert response.status_code == 410
    payload = response.json()
    assert payload["detail"]["error"] == "EMAIL_VERIFICATION_DISABLED"


@pytest.mark.asyncio
async def test_register_agent_rejects_duplicate_email(client):
    first_response = await client.post(
        "/api/agents/register",
        json={
            "name": "Unique Name A",
            "email": "duplicate@example.com",
            "model": "gpt-5.4",
            "avatar": "🅰️",
            "style": "测试风格 A",
            "framework": "custom",
        },
    )
    assert first_response.status_code == 200

    register_response = await client.post(
        "/api/agents/register",
        json={
            "name": "Unique Name B",
            "email": "duplicate@example.com",
            "model": "gpt-5.4",
            "avatar": "🅱️",
            "style": "测试风格 B",
            "framework": "custom",
        },
    )

    assert register_response.status_code == 409
    payload = register_response.json()
    assert payload["detail"]["error"] == "EMAIL_ALREADY_USED"


@pytest.mark.asyncio
async def test_register_agent_succeeds_without_active_season(
    client, db_session_factory
):
    """无 active 赛季时仍可注册，不应再触发赛季门禁。"""
    async with db_session_factory() as session:
        result = await session.execute(select(Season))
        seasons = result.scalars().all()
        assert seasons, "seed should create at least one season"
        for season in seasons:
            season.status = "ended"
        await session.commit()

    register_response = await client.post(
        "/api/agents/register",
        json={
            "name": "NoSeasonAgent",
            "email": "noseason@example.com",
            "model": "gpt-5.4",
            "avatar": "📊",
            "style": "测试",
            "framework": "custom",
        },
    )
    assert register_response.status_code == 200
    payload = register_response.json()
    assert payload["agent"]["id"] == "noseasonagent"

    async with db_session_factory() as session:
        accounts_result = await session.execute(
            select(Account).where(Account.agent_id == "noseasonagent")
        )
        accounts = accounts_result.scalars().all()
        assert len(accounts) == 2
        assert all(account.season_id for account in accounts)


@pytest.mark.asyncio
async def test_register_agent_returns_503_on_db_error(client, monkeypatch):
    """测试 DB 异常时返回结构化 503 错误"""

    async def mock_flush(*args, **kwargs):
        raise SQLAlchemyError("Simulated DB error")

    # 模拟 db.flush 抛出异常
    with patch("app.routers.agents.AsyncSession.flush", new=AsyncMock(side_effect=SQLAlchemyError("Simulated DB error"))):
        register_response = await client.post(
            "/api/agents/register",
            json={
                "name": "DBErrorAgent",
                "email": "dberror@example.com",
                "model": "gpt-5.4",
                "avatar": "💥",
                "style": "测试",
                "framework": "custom",
            },
        )

    assert register_response.status_code == 503
    payload = register_response.json()
    assert payload["detail"]["error"] == "REGISTRATION_UNAVAILABLE"
    assert "message" in payload["detail"]
