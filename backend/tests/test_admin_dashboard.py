from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Agent


@pytest.mark.asyncio
async def test_admin_users_endpoint_returns_seeded_user(client, seeded_accounts):
    response = await client.get("/api/admin/users")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert any(item["id"] == seeded_accounts.agent_id for item in payload["items"])
    assert all(item["created_at"].endswith("+00:00") for item in payload["items"] if item.get("created_at"))


@pytest.mark.asyncio
async def test_admin_users_endpoint_hides_deleted_agent(client, seeded_accounts, db_session_factory):
    async with db_session_factory() as session:
        agent = (await session.execute(select(Agent).where(Agent.id == seeded_accounts.agent_id))).scalar_one()
        agent.is_deleted = True
        await session.commit()

    response = await client.get("/api/admin/users")

    assert response.status_code == 200
    payload = response.json()
    assert all(item["id"] != seeded_accounts.agent_id for item in payload["items"])


@pytest.mark.asyncio
async def test_admin_logs_endpoint_returns_trade_logs(client):
    response = await client.get("/api/admin/logs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert payload["buy_total"] >= 1
    assert payload["sell_total"] >= 0
    assert len(payload["items"]) >= 1
    assert "ticker" in payload["items"][0]
    assert "action" in payload["items"][0]
    assert all(item["created_at"].endswith("+00:00") for item in payload["items"] if item.get("created_at"))


@pytest.mark.asyncio
async def test_admin_data_sources_endpoint_returns_status(client):
    response = await client.get("/api/admin/data-sources")

    assert response.status_code == 200
    payload = response.json()
    assert "db" in payload
    assert "redis" in payload
    assert "cache" in payload
    assert "provider_chains" in payload


@pytest.mark.asyncio
async def test_admin_trade_stats_endpoint_returns_totals(client):
    response = await client.get("/api/admin/trade-stats?days=7")

    assert response.status_code == 200
    payload = response.json()
    assert payload["totals"]["trade_count"] >= 1
    assert "daily" in payload
    assert "top_tickers" in payload


@pytest.mark.asyncio
async def test_admin_dashboard_endpoint_returns_all_modules(client):
    response = await client.get("/api/admin/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert "users" in payload
    assert "logs" in payload
    assert "data_sources" in payload
    assert "market" in payload
    assert "trade_stats" in payload
    assert "traffic" in payload
    assert payload["generated_at"].endswith("+00:00")


@pytest.mark.asyncio
async def test_admin_traffic_endpoint_collects_pageview(client):
    post_response = await client.post("/api/analytics/pageview", json={"path": "/leaderboard"})
    assert post_response.status_code == 200
    assert post_response.json()["ok"] is True

    response = await client.get("/api/admin/traffic?days=7&top=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_pv"] >= 1
    assert payload["today_pv"] >= 1
    assert any(item["path"] == "/leaderboard" for item in payload["top_pages"])
