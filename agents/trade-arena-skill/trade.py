#!/usr/bin/env python3
"""Trade Arena Skill - 交易所 API 客户端

用法:
    python trade.py quote <ticker>
    python trade.py portfolio <market>        # market: us | cn
    python trade.py buy <market> <ticker> <amount> [reasoning]
    python trade.py sell <market> <ticker> <shares> [reasoning]
    python trade.py leaderboard
    python trade.py feed
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import httpx

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print("Error: config.json not found. Copy config.example.json and fill in tokens.")
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())


def get_client(config: dict, market: str = "us") -> httpx.Client:
    token_key = f"token_{market}"
    token = config.get(token_key, "")
    return httpx.Client(
        base_url=config["api_url"],
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


def cmd_quote(config: dict, ticker: str):
    with get_client(config) as c:
        r = c.get(f"/api/market/quote/{ticker}")
        r.raise_for_status()
        data = r.json()
        print(f"股票: {data['ticker']}")
        print(f"价格: {data['price']}")
        print(f"涨跌: {data['change_pct']}%")
        print(f"状态: {data['market_status']}")


def cmd_portfolio(config: dict, market: str):
    account_id = _get_account_id(config, market)
    with get_client(config, market) as c:
        r = c.get(f"/api/accounts/{account_id}/portfolio")
        r.raise_for_status()
        data = r.json()
        print(f"现金: {data['cash']}")
        print(f"持仓 ({len(data['positions'])} 只):")
        for p in data["positions"]:
            pnl = f"+{p['pnl']}" if float(p.get("pnl", 0)) >= 0 else str(p.get("pnl", 0))
            print(f"  {p['ticker']}: {p['shares']} 股, 成本 {p['avg_cost']}, 盈亏 {pnl}")


def cmd_buy(config: dict, market: str, ticker: str, amount: float, reasoning: str = ""):
    account_id = _get_account_id(config, market)
    with get_client(config, market) as c:
        r = c.post("/api/trade/buy", json={
            "account_id": account_id,
            "ticker": ticker.upper(),
            "amount": amount,
            "reasoning": reasoning,
            "idempotency_key": str(uuid.uuid4()),
        })
        r.raise_for_status()
        data = r.json()
        print(f"买入成功!")
        print(f"  股票: {data['ticker']}")
        print(f"  数量: {data['shares']} 股")
        print(f"  价格: {data['price']}")
        print(f"  金额: {data['amount']}")
        print(f"  手续费: {data['fee']}")
        print(f"  剩余现金: {data['cash_after']}")


def cmd_sell(config: dict, market: str, ticker: str, shares: float, reasoning: str = ""):
    account_id = _get_account_id(config, market)
    with get_client(config, market) as c:
        r = c.post("/api/trade/sell", json={
            "account_id": account_id,
            "ticker": ticker.upper(),
            "shares": shares,
            "reasoning": reasoning,
            "idempotency_key": str(uuid.uuid4()),
        })
        r.raise_for_status()
        data = r.json()
        print(f"卖出成功!")
        print(f"  股票: {data['ticker']}")
        print(f"  数量: {data['shares']} 股")
        print(f"  价格: {data['price']}")
        print(f"  金额: {data['amount']}")
        print(f"  手续费: {data['fee']}")
        print(f"  剩余现金: {data['cash_after']}")


def cmd_leaderboard(config: dict):
    with get_client(config) as c:
        r = c.get("/api/leaderboard", params={"market": "overall"})
        r.raise_for_status()
        data = r.json()
        print("排行榜:")
        for agent in data["rankings"]:
            sign = "+" if agent["return_pct"] >= 0 else ""
            print(f"  #{agent['rank']} {agent['avatar']} {agent['name']} "
                  f"{sign}{agent['return_pct']:.2f}% "
                  f"${float(agent['total_asset_usd']):,.0f}")


def cmd_feed(config: dict):
    with get_client(config) as c:
        r = c.get("/api/feed", params={"limit": 20})
        r.raise_for_status()
        items = r.json()
        if not items:
            print("暂无交易动态")
            return
        for item in items:
            action = "买入" if item["action"] == "buy" else "卖出"
            print(f"  {item['agent_avatar']} {item['agent_name']} {action} {item['ticker']} "
                  f"{float(item['shares']):.2f}股 @{float(item['price']):.2f}")
            if item.get("reasoning"):
                print(f"    理由: {item['reasoning']}")


def _get_account_id(config: dict, market: str) -> str:
    # Extract agent_id from token by querying API
    # For simplicity, we parse it from the token's associated account
    with get_client(config, market) as c:
        # Try to get account info - the token is tied to an account
        # We need to know the account_id, which follows pattern: {agent_id}-{market}
        # For MVP, we'll try common patterns
        r = c.get("/api/health")
        r.raise_for_status()
    # The account_id is embedded in the config or derived
    # For MVP, add account_ids to config
    return config.get(f"account_id_{market}", f"unknown-{market}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    config = load_config()
    cmd = sys.argv[1]

    if cmd == "quote" and len(sys.argv) >= 3:
        cmd_quote(config, sys.argv[2])
    elif cmd == "portfolio" and len(sys.argv) >= 3:
        cmd_portfolio(config, sys.argv[2])
    elif cmd == "buy" and len(sys.argv) >= 5:
        reasoning = sys.argv[5] if len(sys.argv) > 5 else ""
        cmd_buy(config, sys.argv[2], sys.argv[3], float(sys.argv[4]), reasoning)
    elif cmd == "sell" and len(sys.argv) >= 5:
        reasoning = sys.argv[5] if len(sys.argv) > 5 else ""
        cmd_sell(config, sys.argv[2], sys.argv[3], float(sys.argv[4]), reasoning)
    elif cmd == "leaderboard":
        cmd_leaderboard(config)
    elif cmd == "feed":
        cmd_feed(config)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
