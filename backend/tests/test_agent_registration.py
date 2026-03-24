from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Agent


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
