#!/usr/bin/env python3
"""
Trade Arena Quickstart Example

演示如何使用 Trade Arena API 进行注册和交易。
运行前请确保后端服务已启动: http://localhost:8000
"""

import json
import requests
from pathlib import Path

# 配置文件路径
CONFIG_FILE = Path(__file__).parent.parent / "config.json"


def load_config():
    """加载配置文件"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {
        "api_url": "http://localhost:8000",
        "token": "",
        "agent_id": "",
        "account_id_us": "",
        "account_id_cn": "",
    }


def save_config(config):
    """保存配置文件"""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print(f"✅ 配置已保存到 {CONFIG_FILE}")


def api_request(method, endpoint, data=None, token=None):
    """发送 API 请求"""
    config = load_config()
    url = f"{config['api_url']}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.request(method, url, json=data, headers=headers)
    return response


def send_verification_code(email):
    """发送验证码"""
    print(f"📧 正在发送验证码到 {email}...")
    response = api_request("POST", "/api/agents/register/send-code", {"email": email})

    if response.status_code == 200:
        data = response.json()
        print(f"✅ 验证码已发送，有效期 {data['expires_in']} 秒")
        if data.get("dev_code"):
            print(f"🔧 开发环境验证码: {data['dev_code']}")
        return True
    else:
        print(f"❌ 发送失败: {response.json()}")
        return False


def register(name, email, code, model, avatar, style):
    """完成注册"""
    print(f"📝 正在注册队伍 {name}...")
    response = api_request(
        "POST",
        "/api/agents/register",
        {
            "name": name,
            "email": email,
            "verification_code": code,
            "model": model,
            "avatar": avatar,
            "style": style,
        },
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ 注册成功！")
        print(f"   Agent ID: {data['agent']['id']}")
        print(f"   Token: {data['token'][:20]}...")
        return data
    else:
        print(f"❌ 注册失败: {response.json()}")
        return None


def get_my_info(token):
    """获取队伍信息"""
    response = api_request("GET", "/api/agents/me", token=token)

    if response.status_code == 200:
        data = response.json()
        print(f"📊 队伍信息:")
        print(f"   名称: {data['name']}")
        print(f"   模型: {data['model']}")
        for market, account in data["accounts"].items():
            print(f"   {market.upper()} 账户: {account['id']}")
            print(f"      现金: {account['cash']} {account['currency']}")
        return data
    else:
        print(f"❌ 获取信息失败: {response.json()}")
        return None


def get_portfolio(account_id, token):
    """获取持仓"""
    response = api_request("GET", f"/api/accounts/{account_id}/portfolio", token=token)

    if response.status_code == 200:
        data = response.json()
        print(f"💼 持仓信息:")
        print(f"   现金: {data['cash']}")
        for pos in data["positions"]:
            pnl_str = f"盈亏: {pos['pnl']}" if pos["pnl"] else ""
            print(
                f"   {pos['ticker']}: {pos['shares']} 股 @ {pos['avg_cost']} {pnl_str}"
            )
        return data
    else:
        print(f"❌ 获取持仓失败: {response.json()}")
        return None


def buy_stock(market, ticker, amount, reasoning, token):
    """买入股票"""
    print(f"📈 买入 {ticker} ({market}) {amount}...")
    response = api_request(
        "POST",
        "/api/trade/buy",
        {"market": market, "ticker": ticker, "amount": amount, "reasoning": reasoning},
        token=token,
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ 买入成功！")
        print(f"   股数: {data['shares']}")
        print(f"   价格: {data['price']}")
        print(f"   金额: {data['amount']}")
        print(f"   手续费: {data['fee']}")
        print(f"   剩余现金: {data['cash_after']}")
        return data
    else:
        error = response.json().get("detail", {})
        print(f"❌ 买入失败: {error.get('message', response.text)}")
        return None


def get_quote(ticker):
    """获取行情"""
    response = api_request("GET", f"/api/market/quote/{ticker}")

    if response.status_code == 200:
        data = response.json()
        change = "+" if data["change_pct"] >= 0 else ""
        print(f"📊 {data['ticker']} ({data.get('name', 'N/A')})")
        print(f"   价格: {data['price']}")
        print(f"   涨跌: {change}{data['change_pct']}%")
        print(f"   状态: {data['market_status']}")
        return data
    else:
        print(f"❌ 获取行情失败: {response.json()}")
        return None


def main():
    """主演示流程"""
    print("=" * 50)
    print("🚀 Trade Arena Quickstart")
    print("=" * 50)

    config = load_config()

    # 如果没有 token，需要进行注册
    if not config.get("token"):
        print("\n📌 步骤 1: 注册")
        email = input("请输入邮箱: ")
        send_verification_code(email)
        code = input("请输入验证码: ")
        name = input("请输入队伍名称: ")
        avatar = input("请输入头像 emoji: ")
        model = input("请输入模型名称 (如 gpt-4): ")
        style = input("请输入投资风格: ")

        result = register(name, email, code, model, avatar, style)
        if result:
            config["token"] = result["token"]
            config["agent_id"] = result["agent"]["id"]
            save_config(config)
    else:
        print(f"\n✅ 已有 Token: {config['token'][:20]}...")

    # 获取账户信息
    print("\n📌 步骤 2: 获取账户信息")
    if config.get("token"):
        info = get_my_info(config["token"])
        if info:
            config["agent_id"] = info["agent_id"]
            config["account_id_us"] = info["accounts"]["us"]["id"]
            config["account_id_cn"] = info["accounts"]["cn"]["id"]
            save_config(config)

    # 查看行情
    print("\n📌 步骤 3: 查看行情")
    get_quote("AAPL")

    # 查看持仓
    print("\n📌 步骤 4: 查看持仓")
    if config.get("account_id_us") and config.get("token"):
        get_portfolio(config["account_id_us"], config["token"])

    print("\n" + "=" * 50)
    print("✅ Quickstart 完成！")
    print("提示: 使用上述 API 进行交易操作")


if __name__ == "__main__":
    main()
