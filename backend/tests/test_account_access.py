from __future__ import annotations

import io
import re
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest

import app.auth as auth_module
from app.config import settings
from app.models import Account
from app.schemas import QuoteOut
from app.services import fx as fx_module
from app.services import market_data as md


def _prefer_account_order(
    monkeypatch: pytest.MonkeyPatch, descending: bool = True
) -> None:
    from sqlalchemy import select as sa_select

    def ordered_select(*args, **kwargs):
        statement = sa_select(*args, **kwargs)
        if len(args) == 1 and args[0] is Account:
            order_clause = Account.id.desc() if descending else Account.id.asc()
            return statement.order_by(order_clause)
        return statement

    monkeypatch.setattr(auth_module, "select", ordered_select)


def _read_hosted_skill_version() -> str:
    skill_md = (
        Path(__file__).resolve().parents[2] / "cocoloop-trade-arena" / "SKILL.md"
    )
    content = skill_md.read_text(encoding="utf-8")
    match = re.search(
        r"""(?m)^version:\s*(?:"(?P<dq>[^"]+)"|'(?P<sq>[^']+)'|(?P<raw>[^\s#]+))\s*$""",
        content,
    )
    assert match
    return (match.group("dq") or match.group("sq") or match.group("raw")).strip()


def _mock_quote_map(*tickers: str) -> dict[str, QuoteOut]:
    return {
        ticker: QuoteOut(
            ticker=ticker,
            price=Decimal("198.50"),
            change_pct=1.25,
            volume=1000,
            market_status="open",
        )
        for ticker in tickers
    }


@pytest.mark.asyncio
async def test_shared_token_lists_market_accounts_via_me(client, seeded_accounts):
    response = await client.get(
        "/api/agents/me",
        headers={"Authorization": f"Bearer {seeded_accounts.token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_id"] == seeded_accounts.agent_id
    assert Decimal(str(payload["wallet_cash_cny"])) == Decimal(str(settings.total_starting_capital_cny))
    assert payload["wallet_currency"] == "CNY"
    assert Decimal(str(payload["total_asset_cny"])) >= Decimal(str(settings.total_starting_capital_cny))
    assert payload["accounts"]["us"]["id"] == seeded_accounts.us_account_id
    assert payload["accounts"]["cn"]["id"] == seeded_accounts.cn_account_id
    assert payload["accounts"]["hk"]["id"] == seeded_accounts.hk_account_id
    holdings = {item["market"]: item for item in payload["market_holdings"]}
    assert set(holdings.keys()) == {"us", "cn", "hk"}
    assert holdings["us"]["account_id"] == seeded_accounts.us_account_id
    assert holdings["cn"]["account_id"] == seeded_accounts.cn_account_id
    assert holdings["hk"]["account_id"] == seeded_accounts.hk_account_id


@pytest.mark.asyncio
async def test_agents_list_without_trailing_slash_does_not_redirect(client):
    response = await client.get("/api/agents", follow_redirects=False)

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert any(agent["id"] == "alpha" for agent in payload)


@pytest.mark.asyncio
async def test_shared_token_can_access_primary_account_routes(
    client,
    seeded_accounts,
    monkeypatch: pytest.MonkeyPatch,
):
    _prefer_account_order(monkeypatch, descending=True)

    async def fake_get_quotes_batch(self, tickers: list[str]):
        return _mock_quote_map(*tickers)

    async def fake_get_rate_to_cny(self, market: str):
        if market == "us":
            return Decimal("7.20"), "USD/CNY", None
        if market == "hk":
            return Decimal("0.92"), "HKD/CNY", None
        return Decimal("1"), "CNY/CNY", None

    monkeypatch.setattr(md.MarketDataService, "get_quotes_batch", fake_get_quotes_batch)
    monkeypatch.setattr(fx_module.FXService, "get_rate_to_cny", fake_get_rate_to_cny)

    headers = {"Authorization": f"Bearer {seeded_accounts.token}"}

    account_response = await client.get(
        f"/api/accounts/{seeded_accounts.us_account_id}", headers=headers
    )
    assert account_response.status_code == 200
    account_payload = account_response.json()
    assert account_payload["id"] == seeded_accounts.us_account_id
    assert account_payload["market"] == "us"
    assert account_payload["currency"] == "CNY"
    assert Decimal(str(account_payload["available_cash_cny"])) == Decimal(str(settings.total_starting_capital_cny))

    portfolio_response = await client.get(
        f"/api/accounts/{seeded_accounts.us_account_id}/portfolio",
        headers=headers,
    )
    assert portfolio_response.status_code == 200
    portfolio_payload = portfolio_response.json()
    assert Decimal(str(portfolio_payload["cash"])) == Decimal(str(settings.total_starting_capital_cny))
    assert portfolio_payload["cash_currency"] == "CNY"
    assert portfolio_payload["fx_pair"] == "USD/CNY"
    assert Decimal(str(portfolio_payload["fx_rate"])) == Decimal("7.20")
    assert len(portfolio_payload["positions"]) == 1
    position = portfolio_payload["positions"][0]
    assert position["ticker"] == "AAPL"
    assert Decimal(str(position["current_price"])) == Decimal("1429.20")
    assert Decimal(str(position["pnl"])) == Decimal("97.00")
    assert Decimal(str(position["pnl_cny"])) == Decimal("698.40")

    trades_response = await client.get(
        f"/api/accounts/{seeded_accounts.us_account_id}/trades?limit=5",
        headers=headers,
    )
    assert trades_response.status_code == 200
    trades_payload = trades_response.json()
    assert len(trades_payload) == 1
    assert trades_payload[0]["ticker"] == "AAPL"
    assert trades_payload[0]["action"] == "buy"
    assert trades_payload[0]["created_at"].endswith("+00:00")


@pytest.mark.asyncio
async def test_shared_token_can_access_secondary_account_routes(
    client,
    seeded_accounts,
    monkeypatch: pytest.MonkeyPatch,
):
    _prefer_account_order(monkeypatch, descending=False)

    async def fake_get_quotes_batch(self, tickers: list[str]):
        return _mock_quote_map(*tickers)

    async def fake_get_rate_to_cny(self, market: str):
        if market == "us":
            return Decimal("7.20"), "USD/CNY", None
        if market == "hk":
            return Decimal("0.92"), "HKD/CNY", None
        return Decimal("1"), "CNY/CNY", None

    monkeypatch.setattr(md.MarketDataService, "get_quotes_batch", fake_get_quotes_batch)
    monkeypatch.setattr(fx_module.FXService, "get_rate_to_cny", fake_get_rate_to_cny)

    headers = {"Authorization": f"Bearer {seeded_accounts.token}"}

    account_response = await client.get(
        f"/api/accounts/{seeded_accounts.cn_account_id}",
        headers=headers,
    )
    assert account_response.status_code == 200
    account_payload = account_response.json()
    assert account_payload["id"] == seeded_accounts.cn_account_id
    assert account_payload["market"] == "cn"
    assert account_payload["currency"] == "CNY"

    portfolio_response = await client.get(
        f"/api/accounts/{seeded_accounts.cn_account_id}/portfolio",
        headers=headers,
    )
    assert portfolio_response.status_code == 200
    portfolio_payload = portfolio_response.json()
    expected_cny_cash = Decimal(str(settings.total_starting_capital_cny))
    assert Decimal(str(portfolio_payload["cash"])) == expected_cny_cash
    assert portfolio_payload["cash_currency"] == "CNY"
    assert portfolio_payload["fx_pair"] == "CNY/CNY"
    assert Decimal(str(portfolio_payload["fx_rate"])) == Decimal("1")
    assert portfolio_payload["positions"] == []

    trades_response = await client.get(
        f"/api/accounts/{seeded_accounts.cn_account_id}/trades?limit=5",
        headers=headers,
    )
    assert trades_response.status_code == 200
    trades_payload = trades_response.json()
    assert len(trades_payload) == 1
    assert trades_payload[0]["ticker"] == "600519.SH"
    assert trades_payload[0]["action"] == "buy"
    assert trades_payload[0]["created_at"].endswith("+00:00")


@pytest.mark.asyncio
async def test_template_download_endpoint_is_retired(client, seeded_accounts):
    response = await client.get("/api/agents/template/download")

    assert response.status_code == 410
    payload = response.json()
    assert payload["detail"]["error"] == "TEMPLATE_RETIRED"


@pytest.mark.asyncio
async def test_skill_download_endpoint_returns_installable_archive(client):
    response = await client.get("/api/agents/skill/download")

    assert response.status_code == 200
    assert (
        response.headers["content-disposition"]
        == "attachment; filename=cocoloop-trade-arena.zip"
    )

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    file_list = sorted(archive.namelist())
    assert "SKILL.md" in file_list
    assert "config.json" in file_list
    assert "scripts/quickstart.py" in file_list
    assert "tools/tools.json" in file_list


@pytest.mark.asyncio
async def test_skill_hosted_endpoint_returns_cocoloop_archive(client):
    response = await client.get("/api/agents/skill/hosted")

    assert response.status_code == 200
    assert (
        response.headers["content-disposition"]
        == "attachment; filename=cocoloop-trade-arena.zip"
    )

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    file_list = sorted(archive.namelist())
    assert "SKILL.md" in file_list
    assert "config.json" in file_list
    assert "scripts/quickstart.py" in file_list
    assert "tools/tools.json" in file_list
    assert "references/api.md" in file_list
    assert "references/errors.md" in file_list


@pytest.mark.asyncio
async def test_skill_version_endpoint_returns_version_and_hosted_url(client):
    response = await client.get("/api/agents/skill/version")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == _read_hosted_skill_version()
    assert payload["hosted_url"].endswith("/api/agents/skill/hosted")


@pytest.mark.asyncio
async def test_skill_version_endpoint_prefers_https_for_public_forwarded_origin(client):
    response = await client.get(
        "/api/agents/skill/version",
        headers={
            "host": "stock.cocoloop.cn",
            "x-forwarded-proto": "https",
            "x-forwarded-host": "stock.cocoloop.cn",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["hosted_url"] == "https://stock.cocoloop.cn/api/agents/skill/hosted"


@pytest.mark.asyncio
async def test_static_file_endpoint_returns_hosted_skill_archive_with_fallback(
    client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setattr(settings, "hosted_files_dir", str(tmp_path))
    monkeypatch.setattr(settings, "hosted_skill_filename", "cocoloop-trade-arena.zip")

    response = await client.get("/api/file/cocoloop-trade-arena.zip")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert "SKILL.md" in archive.namelist()
    assert (tmp_path / "cocoloop-trade-arena.zip").exists()


@pytest.mark.asyncio
async def test_static_file_endpoint_prefers_existing_file(
    client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setattr(settings, "hosted_files_dir", str(tmp_path))
    file_path = tmp_path / "custom.zip"
    file_path.write_bytes(b"custom-content")

    response = await client.get("/api/file/custom.zip")

    assert response.status_code == 200
    assert response.content == b"custom-content"
