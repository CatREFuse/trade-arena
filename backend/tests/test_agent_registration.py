from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models import Account, Agent, Wallet


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
@pytest.mark.parametrize(
    ("name", "avatar", "style", "expected_field"),
    [
        ("???", "🚀", "趋势交易", "name"),
        ("Valid Name", "??", "趋势交易", "avatar"),
        ("Valid Name", "🚀", "??????", "style"),
        ("Valid Name", "🚀", "长期持有�风控", "style"),
    ],
)
async def test_register_agent_rejects_placeholder_or_garbled_inputs(
    client, name, avatar, style, expected_field
):
    response = await client.post(
        "/api/agents/register",
        json={
            "name": name,
            "email": f"{expected_field}.invalid@example.com",
            "model": "gpt-5.4",
            "avatar": avatar,
            "style": style,
            "framework": "custom",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    error_fields = [item.get("loc", [])[-1] for item in payload.get("detail", [])]
    assert expected_field in error_fields


@pytest.mark.asyncio
async def test_register_agent_creates_accounts_and_wallet(
    client, db_session_factory
):
    register_response = await client.post(
        "/api/agents/register",
        json={
            "name": "PortfolioAgent",
            "email": "portfolio@example.com",
            "model": "gpt-5.4",
            "avatar": "📊",
            "style": "测试",
            "framework": "custom",
        },
    )
    assert register_response.status_code == 200
    payload = register_response.json()
    assert payload["agent"]["id"] == "portfolioagent"

    async with db_session_factory() as session:
        accounts_result = await session.execute(
            select(Account).where(Account.agent_id == "portfolioagent")
        )
        accounts = accounts_result.scalars().all()
        assert len(accounts) == 3
        assert {account.market for account in accounts} == {"us", "cn", "hk"}
        wallet_result = await session.execute(
            select(Wallet).where(Wallet.agent_id == "portfolioagent")
        )
        wallet = wallet_result.scalar_one_or_none()
        assert wallet is not None


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


@pytest.mark.asyncio
async def test_cleanup_regression_agent_deletes_registered_data(client, db_session_factory):
    register_response = await client.post(
        "/api/agents/register",
        json={
            "name": "regress-999001",
            "email": "regress.999001@example.com",
            "model": "gpt-5.4",
            "avatar": "🧪",
            "style": "回归测试",
            "framework": "custom",
        },
    )
    assert register_response.status_code == 200
    payload = register_response.json()
    token = payload["token"]
    agent_id = payload["agent"]["id"]

    cleanup_response = await client.delete(
        "/api/agents/me/regression",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cleanup_response.status_code == 200
    cleanup_payload = cleanup_response.json()
    assert cleanup_payload["status"] == "deleted"
    assert cleanup_payload["agent_id"] == agent_id

    async with db_session_factory() as session:
        agent_result = await session.execute(select(Agent).where(Agent.id == agent_id))
        agent = agent_result.scalar_one()
        assert agent.is_deleted is True
        assert agent.deleted_at is not None
        assert agent.deleted_by == "api:/api/agents/me/regression"
        assert agent.delete_reason == "regression cleanup"

        account_result = await session.execute(select(Account).where(Account.agent_id == agent_id))
        accounts = account_result.scalars().all()
        assert len(accounts) == 3

        wallet_result = await session.execute(select(Wallet).where(Wallet.agent_id == agent_id))
        assert wallet_result.scalar_one_or_none() is not None

    me_response = await client.get(
        "/api/agents/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 401
    assert me_response.json()["detail"]["error"] == "INVALID_TOKEN"
