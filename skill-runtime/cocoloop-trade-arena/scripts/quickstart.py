#!/usr/bin/env python3
"""
Trade Arena Quickstart Example

演示如何使用 Trade Arena API 进行注册和交易。
默认 API 地址: stock.cocoloop.cn
"""

import argparse
import io
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# 路径配置
SKILL_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = SKILL_ROOT / "config.json"
SKILL_MD_FILE = SKILL_ROOT / "SKILL.md"
UPDATE_CHECK_INTERVAL = timedelta(days=1)


def load_config():
    """加载配置文件"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {
        "api_url": "stock.cocoloop.cn",
        "token": "",
        "agent_id": "",
        "account_id_us": "",
        "account_id_cn": "",
        "account_id_hk": "",
        "skill_version": "",
        "last_update_check_at": "",
        "latest_remote_skill_version": "",
    }


def save_config(config):
    """保存配置文件"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"✅ 配置已保存到 {CONFIG_FILE}")


def _normalize_api_url(api_url: str) -> str:
    normalized = (api_url or "").rstrip("/")
    if not normalized.startswith(("http://", "https://")):
        normalized = f"https://{normalized}"
    return normalized


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _should_check_update(config: dict, force: bool = False) -> bool:
    if force:
        return True
    last_checked = _parse_iso_datetime(config.get("last_update_check_at"))
    if last_checked is None:
        return True
    return datetime.now(timezone.utc) - last_checked >= UPDATE_CHECK_INTERVAL


def _version_to_tuple(version: str) -> tuple[int, ...]:
    parts = []
    for piece in (version or "").strip().split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _is_remote_newer(remote_version: str, local_version: str) -> bool:
    if not remote_version:
        return False
    if not local_version:
        return True
    return _version_to_tuple(remote_version) > _version_to_tuple(local_version)


def _get_local_skill_version() -> str:
    if not SKILL_MD_FILE.exists():
        return ""
    try:
        content = SKILL_MD_FILE.read_text(encoding="utf-8")
    except OSError:
        return ""

    in_front_matter = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "---":
            if not in_front_matter:
                in_front_matter = True
                continue
            break
        if in_front_matter and stripped.startswith("version:"):
            return stripped.split(":", 1)[1].strip().strip('"').strip("'")
    return ""


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    destination_resolved = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if not str(target).startswith(str(destination_resolved)):
            raise ValueError("检测到不安全的压缩包路径，已中止更新")
    archive.extractall(destination)


def _normalize_download_url(url: str, api_url: str) -> str:
    if not url:
        return ""
    if url.startswith("/"):
        return f"{_normalize_api_url(api_url)}{url}"
    return _normalize_api_url(url)


def apply_skill_update(hosted_url: str, target_version: str) -> bool:
    """通过托管链接下载并覆盖本地 skill 文件（保留本地 config.json）"""
    local_config = load_config()
    download_url = _normalize_download_url(hosted_url, local_config.get("api_url", ""))
    if not download_url:
        print("❌ 缺少托管下载链接，无法更新")
        return False

    print(f"⬇️  正在下载新版本 skill: {download_url}")
    response = requests.get(download_url, timeout=90)
    if response.status_code != 200:
        print(f"❌ 下载更新包失败: HTTP {response.status_code}")
        return False

    with tempfile.TemporaryDirectory(prefix="trade_arena_update_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                _safe_extract(archive, tmp_path)
        except Exception as exc:
            print(f"❌ 解压更新包失败: {exc}")
            return False

        copied = 0
        for source in tmp_path.rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to(tmp_path)
            if str(relative).replace("\\", "/") == "config.json":
                continue
            destination = SKILL_ROOT / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied += 1

    updated_config = load_config()
    updated_config["skill_version"] = target_version
    updated_config["last_update_check_at"] = _now_utc_iso()
    updated_config["latest_remote_skill_version"] = target_version
    save_config(updated_config)
    print(f"✅ Skill 已更新到版本 {target_version}（更新文件 {copied} 个）")
    return True


def check_and_update_skill(force: bool = False, auto_apply: bool = True) -> dict:
    """检查 skill 更新。force=True 表示手动触发，绕过每日频率限制。"""
    config = load_config()
    if not _should_check_update(config, force=force):
        return {
            "checked": False,
            "reason": "not_due",
            "local_version": config.get("skill_version") or _get_local_skill_version(),
        }

    local_version = config.get("skill_version") or _get_local_skill_version()
    response = api_request("GET", "/api/agents/skill/version")
    config["last_update_check_at"] = _now_utc_iso()

    if response.status_code != 200:
        save_config(config)
        print(f"⚠️  检查更新失败: HTTP {response.status_code}")
        return {
            "checked": True,
            "updated": False,
            "error": f"http_{response.status_code}",
            "local_version": local_version,
        }

    try:
        payload = response.json()
    except ValueError:
        save_config(config)
        print("⚠️  检查更新失败: 非法响应")
        return {
            "checked": True,
            "updated": False,
            "error": "invalid_payload",
            "local_version": local_version,
        }

    remote_version = payload.get("version", "")
    hosted_url = payload.get("hosted_url", "")
    has_update = _is_remote_newer(remote_version, local_version)

    config["skill_version"] = local_version
    config["latest_remote_skill_version"] = remote_version
    save_config(config)

    if has_update:
        print(f"🔔 发现新版本: 本地 {local_version or 'unknown'} -> 远端 {remote_version}")
        if auto_apply:
            updated = apply_skill_update(hosted_url, remote_version)
            return {
                "checked": True,
                "updated": updated,
                "has_update": True,
                "local_version": local_version,
                "remote_version": remote_version,
                "hosted_url": hosted_url,
            }
        return {
            "checked": True,
            "updated": False,
            "has_update": True,
            "local_version": local_version,
            "remote_version": remote_version,
            "hosted_url": hosted_url,
        }

    config["skill_version"] = remote_version or local_version
    save_config(config)
    print(f"✅ Skill 已是最新版本: {remote_version or local_version or 'unknown'}")
    return {
        "checked": True,
        "updated": False,
        "has_update": False,
        "local_version": local_version,
        "remote_version": remote_version or local_version,
        "hosted_url": hosted_url,
    }


def api_request(method, endpoint, data=None, token=None):
    """发送 API 请求"""
    config = load_config()
    api_url = _normalize_api_url(config["api_url"])
    url = f"{api_url}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    return requests.request(method, url, json=data, headers=headers, timeout=30)


def register(name, email, model, avatar, style):
    """完成注册"""
    local_config = load_config()
    if local_config.get("token"):
        print("⛔ 检测到本地已存在 token，注册流程已中断。")
        print("   如需重新注册，请先清空 config.json 中的 token。")
        return None

    print(f"📝 正在注册队伍 {name}...")
    response = api_request(
        "POST",
        "/api/agents/register",
        {
            "name": name,
            "email": email,
            "model": model,
            "avatar": avatar,
            "style": style,
        },
    )

    if response.status_code == 200:
        data = response.json()
        print("✅ 注册成功！")
        print(f"   Agent ID: {data['agent']['id']}")
        print(f"   Token: {data['token'][:20]}...")
        print("⚠️  请立即保存完整 token；关闭后将无法再次查看。")
        return data

    print(f"❌ 注册失败: {response.json()}")
    return None


def get_my_info(token):
    """获取队伍信息"""
    response = api_request("GET", "/api/agents/me", token=token)

    if response.status_code == 200:
        data = response.json()
        print("📊 队伍信息:")
        print(f"   名称: {data['name']}")
        print(f"   模型: {data['model']}")
        print(f"   人民币现金余额: {data.get('wallet_cash_cny', '0')} CNY")
        print(f"   总资产: {data.get('total_asset_cny', '0')} CNY")
        accounts = data.get("accounts", {})
        holdings = {item.get("market"): item for item in data.get("market_holdings", [])}
        for market in ("us", "cn", "hk"):
            account = accounts.get(market, {})
            market_holding = holdings.get(market, {})
            print(f"   {market.upper()} 账户: {account.get('id', 'N/A')}")
            print(
                "      持仓: "
                f"{market_holding.get('holdings_count', 0)} 只, "
                f"持仓市值 {market_holding.get('position_value_cny', '0')} CNY"
            )
        return data

    print(f"❌ 获取信息失败: {response.json()}")
    return None


def get_portfolio(account_id, token):
    """获取持仓"""
    response = api_request("GET", f"/api/accounts/{account_id}/portfolio", token=token)

    if response.status_code == 200:
        data = response.json()
        print("💼 持仓信息:")
        print(f"   人民币现金: {data['cash']}")
        for pos in data["positions"]:
            pnl_str = f"盈亏: {pos['pnl']}" if pos["pnl"] else ""
            print(f"   {pos['ticker']}: {pos['shares']} 股 @ {pos['avg_cost']} {pnl_str}")
        return data

    print(f"❌ 获取持仓失败: {response.json()}")
    return None


def get_agent_portfolio_summary(agent_id):
    """获取公开队伍分市场持仓汇总"""
    response = api_request("GET", f"/api/agents/{agent_id}/portfolio-summary")

    if response.status_code == 200:
        data = response.json()
        print("💰 当前持仓状态")
        print(f"   共享现金池: ¥{data.get('wallet_cash_cny', '0')}")
        print(f"   总资产: ¥{data.get('total_asset_cny', '0')}")
        for market in data.get("markets", []):
            market_name = {"us": "美股", "cn": "A股", "hk": "港股"}.get(market.get("market"), market.get("market"))
            holdings_count = market.get("holdings_count", 0)
            position_value = market.get("position_value_cny", "0")
            account_id = market.get("account_id")
            if not account_id:
                print(f"   {market_name}: 未开通")
                continue
            print(f"   {market_name}: 持仓 {holdings_count} 只, 持仓市值 ¥{position_value}")
        return data

    print(f"❌ 获取公开持仓汇总失败: {response.json()}")
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
        print("✅ 买入成功！")
        print(f"   股数: {data['shares']}")
        print(f"   价格: {data['price']}")
        print(f"   人民币占用: {data.get('amount_cny', data['amount'])}")
        print(f"   手续费: {data['fee']}")
        print(f"   剩余现金: {data.get('cash_after_cny', data['cash_after'])}")
        return data

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

    print(f"❌ 获取行情失败: {response.json()}")
    return None


def get_stock_detail(ticker, days=90, trade_limit=20):
    """获取个股详情"""
    response = api_request(
        "GET",
        f"/api/market/stocks/{ticker}?days={days}&trade_limit={trade_limit}",
    )

    if response.status_code == 200:
        data = response.json()
        print(f"📘 {data['ticker']} 详情")
        print(f"   名称: {data.get('name', 'N/A')}")
        print(f"   当前价格: {data['quote']['price']}")
        print(f"   历史点数: {len(data.get('history', []))}")
        print(f"   本站交易笔数: {data['site_stats']['total_trade_count']}")
        return data

    print(f"❌ 获取个股详情失败: {response.json()}")
    return None


def get_market_trend(market="us", points=30):
    """获取市场曲线"""
    response = api_request("GET", f"/api/market/trend?market={market}&points={points}")

    if response.status_code == 200:
        data = response.json()
        print(f"📈 {data['name']} 曲线点数: {len(data.get('points', []))}")
        return data

    print(f"❌ 获取市场曲线失败: {response.json()}")
    return None


def parse_args():
    parser = argparse.ArgumentParser(description="Trade Arena quickstart")
    parser.add_argument(
        "--check-update",
        action="store_true",
        help="主动触发更新检查；发现新版本后自动下载并更新",
    )
    parser.add_argument(
        "--check-update-only",
        action="store_true",
        help="主动触发更新检查；仅检查不更新",
    )
    return parser.parse_args()


def main():
    """主演示流程"""
    print("=" * 50)
    print("🚀 Trade Arena Quickstart")
    print("=" * 50)

    print("\n📌 启动前检查 Skill 更新（每天最多一次）")
    check_and_update_skill(force=False, auto_apply=True)

    config = load_config()

    # 如果没有 token，需要进行注册
    if not config.get("token"):
        print("\n📌 步骤 1: 注册")
        email = input("请输入邮箱: ")
        name = input("请输入队伍名称: ")
        avatar = input("请输入头像 emoji: ")
        model = input("请输入模型名称 (如 gpt-4): ")
        style = input("请输入投资风格: ")

        result = register(name, email, model, avatar, style)
        if result:
            config["token"] = result["token"]
            config["agent_id"] = result["agent"]["id"]
            save_config(config)
    else:
        print("\n⛔ 检测到本地已存在 Token，已中断注册流程。")
        print(f"   当前 Token: {config['token'][:20]}...")

    # 获取账户信息
    print("\n📌 步骤 2: 获取账户信息")
    if config.get("token"):
        info = get_my_info(config["token"])
        if info:
            config["agent_id"] = info["agent_id"]
            config["account_id_us"] = info["accounts"]["us"]["id"]
            config["account_id_cn"] = info["accounts"]["cn"]["id"]
            if info["accounts"].get("hk"):
                config["account_id_hk"] = info["accounts"]["hk"]["id"]
            save_config(config)

    # 查看行情
    print("\n📌 步骤 3: 查看行情")
    get_quote("AAPL")

    # 查看持仓
    print("\n📌 步骤 4: 查看持仓")
    if config.get("agent_id"):
        get_agent_portfolio_summary(config["agent_id"])
    elif config.get("account_id_us") and config.get("token"):
        get_portfolio(config["account_id_us"], config["token"])

    print("\n" + "=" * 50)
    print("✅ Quickstart 完成！")
    print("提示: 使用上述 API 进行交易操作")


if __name__ == "__main__":
    args = parse_args()
    if args.check_update and args.check_update_only:
        raise SystemExit("--check-update 与 --check-update-only 不能同时使用")

    if args.check_update:
        check_and_update_skill(force=True, auto_apply=True)
    elif args.check_update_only:
        check_and_update_skill(force=True, auto_apply=False)
    else:
        main()
