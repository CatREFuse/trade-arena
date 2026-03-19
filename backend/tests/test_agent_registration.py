from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Agent


@pytest.mark.asyncio
async def test_send_email_code_and_register_agent_success(client, db_session_factory):
    send_response = await client.post(
        "/api/agents/register/send-code",
        json={"email": "player@example.com"},
    )

    assert send_response.status_code == 200
    send_payload = send_response.json()
    assert send_payload["email"] == "player@example.com"
    assert send_payload["delivery"] == "dev"
    assert len(send_payload["dev_code"]) == 6

    register_response = await client.post(
        "/api/agents/register",
        json={
            "name": "Player One",
            "email": "player@example.com",
            "verification_code": send_payload["dev_code"],
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
        assert agent.email_verified_at is not None


@pytest.mark.asyncio
async def test_register_agent_rejects_invalid_verification_code(client):
    send_response = await client.post(
        "/api/agents/register/send-code",
        json={"email": "wrong-code@example.com"},
    )
    assert send_response.status_code == 200

    register_response = await client.post(
        "/api/agents/register",
        json={
            "name": "Wrong Code",
            "email": "wrong-code@example.com",
            "verification_code": "000000",
            "model": "gpt-5.4",
            "avatar": "🧪",
            "style": "测试风格",
            "framework": "custom",
        },
    )

    assert register_response.status_code == 400
    payload = register_response.json()
    assert payload["detail"]["error"] == "INVALID_VERIFICATION_CODE"
