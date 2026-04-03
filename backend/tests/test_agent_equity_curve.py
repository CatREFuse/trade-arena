from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_agent_equity_curve_defaults_to_chart_type_span(client, seeded_accounts):
    response = await client.get(
        f"/api/agents/{seeded_accounts.agent_id}/equity-curve",
        params={"chart_type": "intraday"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["span"] == "1d"
    assert payload["interval"] == "5m"
    assert len(payload["points"]) >= 2
    assert payload["points"][0]["value"] == payload["points"][-1]["value"]


@pytest.mark.asyncio
async def test_agent_chart_legacy_endpoint_maps_days_to_span(client, seeded_accounts):
    response = await client.get(
        f"/api/agents/{seeded_accounts.agent_id}/chart",
        params={"days": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 2
    assert payload[0]["value"] == payload[-1]["value"]
