#!/usr/bin/env python3
"""
Trade Arena Quickstart Example

演示如何使用 Trade Arena API 进行注册和交易。
默认 API 地址: stock.cocoloop.cn
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import requests

SKILL_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = SKILL_ROOT / "config.json"
SKILL_MD_FILE = SKILL_ROOT / "SKILL.md"
STRATEGY_FILE = SKILL_ROOT / "strategy.md"
LEGACY_STRATEGY_FILE = SKILL_ROOT / "strategy.MD"
LANDING_REQUIRED_VERSIONS = {"1.3.0"}
LANDING_RECALL_LINES = [
    "之后你随时都可以重新叫起这套设置流。",
    "常用说法：配置 trade arena / 修改我的投资策略 / 重新生成定时任务建议",
]
LANDING_CAPABILITY_LINES = [
    "你现在已经接入了 Trade Arena。",
    "它可以帮你查看账户现金和三地持仓，跟踪个股、指数和市场状态，也能直接执行买入卖出。",
    "你还可以查看排行榜、资产变化，并把自己的投资策略写成一份长期可复用的 strategy.md。",
    "这一版开始，Skill 还会结合当前宿主环境，帮你生成更适合落地的定时任务建议。",
]
USER_EXAMPLE_LINES = [
    "看看我的账户现金和三地持仓",
    "看看 AAPL 股票的情况",
    "查看今天的大盘情况，并做个总结",
    "查看今天的排行榜",
    "我的资产动态是怎么样的",
    "根据大盘和搜索结果自主买进 ...",
]
CUSTOM_TOKENS = {"/custom", "我自己定义", "自定义"}
LATER_TOKENS = {"/later", "稍后再说", "稍后"}


@dataclass
class StrategyState:
    exists: bool
    valid: bool
    path: Path | None
    content: str
    reason: str = ""


@dataclass
class StartupGateResult:
    config: dict
    local_version: str
    remote_version: str
    update_checked: bool = False
    updated: bool = False
    update_error: str = ""
    should_run_landing: bool = False
    landing_reason: str = ""
    strategy_state: StrategyState | None = None
    migration_required: bool = False


@dataclass
class SchedulePlan:
    capability: str
    base_lines: list[str]
    market_lines: list[str]
    actionable_lines: list[str]
    custom_request: str = ""


InputFunc = Callable[[str], str]


def _default_setup_state() -> dict:
    return {
        "landing_last_seen_version": "",
        "landing_last_completed_version": "",
        "strategy_last_updated_at": "",
        "strategy_capture_mode": "",
        "schedule_last_generated_at": "",
        "runtime_capability": "",
        "last_update_error": "",
    }


def default_config() -> dict:
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
        "setup_state": _default_setup_state(),
    }


def _merge_setup_state(raw_setup: dict | None) -> dict:
    merged = _default_setup_state()
    if isinstance(raw_setup, dict):
        for key in merged:
            value = raw_setup.get(key)
            if isinstance(value, str):
                merged[key] = value
    return merged


def _normalize_config_payload(raw: object) -> dict:
    config = default_config()
    if not isinstance(raw, dict):
        return config

    # The source package used to ship a JSON schema in config.json.
    if raw.get("$schema") and raw.get("properties") and "api_url" not in raw:
        return config

    for key in config:
        if key == "setup_state":
            continue
        value = raw.get(key)
        if isinstance(value, str):
            config[key] = value
    config["setup_state"] = _merge_setup_state(raw.get("setup_state"))
    return config


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return default_config()
    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_config()
    return _normalize_config_payload(raw)


def save_config(config: dict, announce: bool = True) -> None:
    normalized = _normalize_config_payload(config)
    CONFIG_FILE.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if announce:
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


def apply_skill_update(hosted_url: str, target_version: str, silent: bool = False) -> bool:
    """通过托管链接下载并覆盖本地 skill 文件（保留本地 config.json 与 strategy.md）"""
    local_config = load_config()
    download_url = _normalize_download_url(hosted_url, local_config.get("api_url", ""))
    if not download_url:
        if not silent:
            print("❌ 缺少托管下载链接，无法更新")
        return False

    if not silent:
        print(f"⬇️  正在下载新版本 skill: {download_url}")
    response = requests.get(download_url, timeout=90)
    if response.status_code != 200:
        if not silent:
            print(f"❌ 下载更新包失败: HTTP {response.status_code}")
        return False

    with tempfile.TemporaryDirectory(prefix="trade_arena_update_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                _safe_extract(archive, tmp_path)
        except Exception as exc:
            if not silent:
                print(f"❌ 解压更新包失败: {exc}")
            return False

        copied = 0
        protected = {"config.json", "strategy.md", "strategy.MD"}
        for source in tmp_path.rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to(tmp_path)
            if str(relative).replace("\\", "/") in protected:
                continue
            destination = SKILL_ROOT / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied += 1

    updated_config = load_config()
    updated_config["skill_version"] = target_version
    updated_config["last_update_check_at"] = _now_utc_iso()
    updated_config["latest_remote_skill_version"] = target_version
    updated_config["setup_state"]["last_update_error"] = ""
    save_config(updated_config, announce=False)
    print(f"✅ 已自动更新到最新版 {target_version}（更新文件 {copied} 个）")
    return True


def check_and_update_skill(force: bool = False, auto_apply: bool = True, silent: bool = False) -> dict:
    """检查 skill 更新。默认每次主动运行都检查一次。"""
    config = load_config()
    local_version = config.get("skill_version") or _get_local_skill_version()
    config["skill_version"] = local_version
    config["last_update_check_at"] = _now_utc_iso()

    try:
        response = api_request("GET", "/api/agents/skill/version")
    except requests.RequestException as exc:
        config["setup_state"]["last_update_error"] = exc.__class__.__name__
        save_config(config, announce=False)
        if force and not silent:
            print(f"⚠️  检查更新失败: {exc}")
        return {
            "checked": True,
            "updated": False,
            "error": exc.__class__.__name__,
            "local_version": local_version,
        }

    if response.status_code != 200:
        config["setup_state"]["last_update_error"] = f"http_{response.status_code}"
        save_config(config, announce=False)
        if force and not silent:
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
        config["setup_state"]["last_update_error"] = "invalid_payload"
        save_config(config, announce=False)
        if force and not silent:
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

    config["latest_remote_skill_version"] = remote_version
    config["setup_state"]["last_update_error"] = ""
    save_config(config, announce=False)

    if has_update:
        updated = False
        if auto_apply:
            updated = apply_skill_update(hosted_url, remote_version, silent=silent)
        elif not silent:
            print(f"🔔 发现新版本: 本地 {local_version or 'unknown'} -> 远端 {remote_version}")
        return {
            "checked": True,
            "updated": updated,
            "has_update": True,
            "local_version": local_version,
            "remote_version": remote_version,
            "hosted_url": hosted_url,
        }

    if force and not silent:
        print(f"✅ Skill 已是最新版本: {remote_version or local_version or 'unknown'}")
    return {
        "checked": True,
        "updated": False,
        "has_update": False,
        "local_version": local_version,
        "remote_version": remote_version or local_version,
        "hosted_url": hosted_url,
    }


def read_strategy_document() -> StrategyState:
    for path in (STRATEGY_FILE, LEGACY_STRATEGY_FILE):
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return StrategyState(True, False, path, "", "unreadable")
        if not content.strip():
            return StrategyState(True, False, path, content, "empty")
        return StrategyState(True, True, path, content, "")
    return StrategyState(False, False, None, "", "missing")


def write_strategy_document(content: str) -> Path:
    normalized = content.strip() + "\n"
    STRATEGY_FILE.write_text(normalized, encoding="utf-8")
    if LEGACY_STRATEGY_FILE.exists() and LEGACY_STRATEGY_FILE != STRATEGY_FILE:
        try:
            LEGACY_STRATEGY_FILE.unlink()
        except OSError:
            pass
    return STRATEGY_FILE


def summarize_strategy(strategy_text: str) -> str:
    lines = [line.strip() for line in strategy_text.splitlines() if line.strip()]
    if not lines:
        return "还没有有效策略。"
    summary_lines = lines[:4]
    if len(lines) > 4:
        summary_lines.append("后续还有更完整的执行细节。")
    return "\n".join(summary_lines)


def _current_version_requires_landing(version: str) -> bool:
    return version in LANDING_REQUIRED_VERSIONS


def run_startup_gate(force_landing: bool = False) -> StartupGateResult:
    update_result = check_and_update_skill(force=True, auto_apply=True, silent=True)
    config = load_config()
    local_version = config.get("skill_version") or _get_local_skill_version()
    config["skill_version"] = local_version
    strategy_state = read_strategy_document()
    setup_state = config["setup_state"]
    migration_required = (
        _current_version_requires_landing(local_version)
        and setup_state.get("landing_last_seen_version") != local_version
    )

    landing_reason = ""
    should_run_landing = force_landing
    if not strategy_state.exists:
        should_run_landing = True
        landing_reason = "missing_strategy"
    elif not strategy_state.valid:
        should_run_landing = True
        landing_reason = "broken_strategy"
    elif migration_required:
        should_run_landing = True
        landing_reason = "migration"
    elif force_landing:
        should_run_landing = True
        landing_reason = "manual"

    save_config(config, announce=False)
    return StartupGateResult(
        config=config,
        local_version=local_version,
        remote_version=update_result.get("remote_version", local_version),
        update_checked=bool(update_result.get("checked")),
        updated=bool(update_result.get("updated")),
        update_error=update_result.get("error", ""),
        should_run_landing=should_run_landing,
        landing_reason=landing_reason,
        strategy_state=strategy_state,
        migration_required=migration_required,
    )


def mark_landing_seen(config: dict, version: str) -> None:
    config["setup_state"]["landing_last_seen_version"] = version
    save_config(config, announce=False)


def mark_landing_completed(config: dict, version: str) -> None:
    setup_state = config["setup_state"]
    setup_state["landing_last_seen_version"] = version
    setup_state["landing_last_completed_version"] = version
    save_config(config, announce=False)


def api_request(method, endpoint, data=None, token=None):
    config = load_config()
    api_url = _normalize_api_url(config["api_url"])
    url = f"{api_url}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.request(method, url, json=data, headers=headers, timeout=30)


def register(name, email, model, avatar, style):
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
    response = api_request("GET", f"/api/market/trend?market={market}&points={points}")

    if response.status_code == 200:
        data = response.json()
        print(f"📈 {data['name']} 曲线点数: {len(data.get('points', []))}")
        return data

    print(f"❌ 获取市场曲线失败: {response.json()}")
    return None


def prompt_choice(prompt: str, choices: dict[str, str], input_fn: InputFunc = input) -> str:
    print(prompt)
    for key, label in choices.items():
        print(f"{key}. {label}")
    while True:
        raw = input_fn("请选择: ").strip()
        if raw in choices:
            return raw
        print("请输入有效编号。")


def prompt_text(prompt: str, input_fn: InputFunc = input) -> str:
    while True:
        raw = input_fn(prompt).strip()
        if raw:
            return raw
        print("这一项先别留空。")


def collect_multiline(prompt: str, input_fn: InputFunc = input) -> str:
    print(prompt)
    print("输入 END 结束。")
    lines: list[str] = []
    while True:
        line = input_fn("").rstrip("\n")
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def build_strategy_markdown(mode: str, answers: dict[str, str]) -> str:
    title = answers.get("title") or "Trade Arena 投资策略"
    sections = [
        ("总体目标", answers.get("goal", "")),
        ("主要关注市场", answers.get("markets", "")),
        ("核心风格与原则", answers.get("style", "")),
        ("建仓与减仓规则", answers.get("positioning", "")),
        ("风险控制", answers.get("risk", "")),
        ("观察重点与触发条件", answers.get("triggers", "")),
        ("调度偏好", answers.get("schedule", "")),
    ]
    lines = [f"# {title}", "", f"策略来源：{mode}", ""]
    for heading, body in sections:
        if not body.strip():
            continue
        lines.append(f"## {heading}")
        lines.append(body.strip())
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def capture_strategy_template(input_fn: InputFunc = input) -> tuple[str, str]:
    answers: dict[str, str] = {"title": "Trade Arena 投资策略"}
    prompts = [
        ("goal", "你的总体目标是什么？"),
        ("markets", "你主要关注哪些市场？"),
        ("style", "你的投资风格和核心原则是什么？"),
        ("positioning", "你打算怎么建仓、加仓和减仓？"),
        ("risk", "你的仓位上限、止损或回撤规则是什么？"),
        ("triggers", "你最看重哪些观察信号和触发条件？"),
        ("schedule", "你希望任务按什么节奏运行？"),
    ]
    for key, prompt in prompts:
        raw = prompt_text(f"{prompt} ", input_fn=input_fn)
        if raw in CUSTOM_TOKENS:
            return capture_strategy_custom(input_fn=input_fn)
        answers[key] = raw
    return build_strategy_markdown("template", answers), "template"


def capture_strategy_guided(input_fn: InputFunc = input) -> tuple[str, str]:
    answers = {
        "title": "Trade Arena 投资策略",
        "goal": prompt_text("这次参赛你最想抓住什么机会？ ", input_fn=input_fn),
        "markets": prompt_text("你更想盯哪些市场，为什么？ ", input_fn=input_fn),
        "style": prompt_text("你通常会在什么情况下出手，又在什么情况下按兵不动？ ", input_fn=input_fn),
        "positioning": prompt_text("如果判断正确或判断失误，你会怎么加减仓？ ", input_fn=input_fn),
        "risk": prompt_text("你最不能接受的风险是什么，打算怎么控？ ", input_fn=input_fn),
        "triggers": prompt_text("你会重点看哪些消息、价格或市场状态？ ", input_fn=input_fn),
        "schedule": prompt_text("你希望系统在什么节奏下提醒或运行？ ", input_fn=input_fn),
    }
    for value in answers.values():
        if value in CUSTOM_TOKENS:
            return capture_strategy_custom(input_fn=input_fn)
    return build_strategy_markdown("guided", answers), "guided"


def capture_strategy_custom(input_fn: InputFunc = input) -> tuple[str, str]:
    body = collect_multiline("请直接贴出你的完整投资策略。", input_fn=input_fn)
    if not body:
        body = "暂未填写完整策略。"
    answers = {
        "title": "Trade Arena 投资策略",
        "goal": body,
    }
    return build_strategy_markdown("custom", answers), "custom"


def confirm_strategy_flow(existing_strategy: str = "", input_fn: InputFunc = input) -> tuple[str | None, str | None]:
    current = existing_strategy
    current_mode = ""
    while True:
        if current:
            print("\n当前策略草稿如下：\n")
            print(current)
            choice = prompt_choice(
                "你想怎么处理这份策略？",
                {"1": "确认写入", "2": "重新生成", "3": "我自己直接写", "4": "稍后再说"},
                input_fn=input_fn,
            )
            if choice == "1":
                return current, current_mode or "custom"
            if choice == "2":
                current = ""
                current_mode = ""
                continue
            if choice == "3":
                current, current_mode = capture_strategy_custom(input_fn=input_fn)
                continue
            return None, None

        mode_choice = prompt_choice(
            "你想怎么整理投资策略？",
            {"1": "轻量模板", "2": "半结构化向导", "3": "我自己直接写"},
            input_fn=input_fn,
        )
        if mode_choice == "1":
            current, current_mode = capture_strategy_template(input_fn=input_fn)
        elif mode_choice == "2":
            current, current_mode = capture_strategy_guided(input_fn=input_fn)
        else:
            current, current_mode = capture_strategy_custom(input_fn=input_fn)


def infer_markets(strategy_text: str) -> list[str]:
    lowered = strategy_text.lower()
    detected: list[str] = []
    mapping = {
        "cn": ["a股", "沪深", "上证", "深证", "中证", "cn"],
        "hk": ["港股", "恒生", ".hk", "hk"],
        "us": ["美股", "纳指", "标普", "道指", "us", "nasdaq", "spx"],
    }
    for market, keywords in mapping.items():
        if any(keyword in lowered for keyword in keywords):
            detected.append(market)
    return detected or ["cn", "hk", "us"]


def classify_strategy_style(strategy_text: str) -> str:
    lowered = strategy_text.lower()
    if any(token in lowered for token in ["日内", "高频", "快进快出", "激进", "短线"]):
        return "active"
    if any(token in lowered for token in ["稳健", "低频", "中长线", "耐心", "防守"]):
        return "steady"
    return "balanced"


def detect_runtime_capability() -> str:
    if os.environ.get("CODEX_HOME") or (Path.home() / ".codex" / "automations").exists():
        return "automation"
    if shutil.which("crontab") or shutil.which("systemctl"):
        return "external_schedule"
    return "unknown"


def _format_us_open_close() -> tuple[str, str]:
    ny_tz = ZoneInfo("America/New_York")
    sh_tz = ZoneInfo("Asia/Shanghai")
    today_ny = datetime.now(ny_tz).date()
    open_ny = datetime.combine(today_ny, datetime.min.time(), tzinfo=ny_tz).replace(hour=9, minute=30)
    close_ny = open_ny.replace(hour=16, minute=0)
    return open_ny.astimezone(sh_tz).strftime("%H:%M"), close_ny.astimezone(sh_tz).strftime("%H:%M")


def _build_base_schedule_lines(style: str) -> list[str]:
    if style == "active":
        return [
            "工作日每天至少巡检三次：开盘前、盘中、收盘前。",
            "遇到大幅波动或关键消息时，加一轮临时复核。",
        ]
    if style == "steady":
        return [
            "工作日每天两次就够：开盘后确认一次，收盘前复核一次。",
            "非重点市场只保留日终复盘，避免频繁打断。",
        ]
    return [
        "工作日每天两到三次：开盘前准备、盘中观察、收盘前复核。",
        "先用统一节奏跑起来，再按重点市场加密。",
    ]


def _build_market_schedule_lines(markets: list[str]) -> list[str]:
    us_open, us_close = _format_us_open_close()
    lines: list[str] = []
    if "cn" in markets:
        lines.append("A股增强版：09:20 看盘前准备，09:45 复核开盘，14:45 复核收盘前仓位。")
    if "hk" in markets:
        lines.append("港股增强版：09:20 看盘前准备，10:00 复核开盘阶段，15:45 复核收盘前仓位。")
    if "us" in markets:
        lines.append(
            f"美股增强版：北京时间 {us_open} 前准备，开盘后 30 分钟复核一次，{us_close} 前再做收盘前检查。"
        )
    return lines


def _build_actionable_lines(capability: str, base_lines: list[str], market_lines: list[str], custom_request: str = "") -> list[str]:
    if capability == "automation":
        head = "直接对当前宿主说：请按下面的节奏为我配置 trade-arena 自动运行。"
    elif capability == "external_schedule":
        head = "当前环境更适合外部调度。你可以把下面这段说明交给 cron 或服务器定时任务入口。"
    else:
        head = "当前没有识别出明确的调度承载方式。先保留这段运行说明，后续交给宿主或工作区里的自动化入口。"
    lines = [head]
    if custom_request:
        lines.append(f"我的自定义要求：{custom_request}")
    lines.extend(base_lines)
    lines.extend(market_lines)
    return lines


def generate_schedule_plan(strategy_text: str, custom_request: str = "") -> SchedulePlan:
    capability = detect_runtime_capability()
    style = classify_strategy_style(strategy_text)
    markets = infer_markets(strategy_text + "\n" + custom_request)
    base_lines = _build_base_schedule_lines(style)
    market_lines = _build_market_schedule_lines(markets)
    actionable_lines = _build_actionable_lines(capability, base_lines, market_lines, custom_request=custom_request)
    return SchedulePlan(
        capability=capability,
        base_lines=base_lines,
        market_lines=market_lines,
        actionable_lines=actionable_lines,
        custom_request=custom_request,
    )


def print_schedule_plan(plan: SchedulePlan) -> None:
    capability_name = {
        "automation": "宿主自带自动化能力",
        "external_schedule": "外部调度更合适",
        "unknown": "调度承载方式暂未识别",
    }.get(plan.capability, plan.capability)
    print("\n🕒 定时任务建议")
    print(f"环境判断：{capability_name}")
    print("基础版：")
    for line in plan.base_lines:
        print(f"- {line}")
    print("市场增强版：")
    for line in plan.market_lines:
        print(f"- {line}")
    print("现在可以直接采用的表达：")
    for line in plan.actionable_lines:
        print(f"- {line}")


def update_schedule_state(config: dict, capability: str) -> None:
    config["setup_state"]["schedule_last_generated_at"] = _now_utc_iso()
    config["setup_state"]["runtime_capability"] = capability
    save_config(config, announce=False)


def run_schedule_flow(strategy_text: str, config: dict, input_fn: InputFunc = input) -> bool:
    print("\n接下来把自动运行这件事也补齐。")
    choice = prompt_choice(
        "你希望我怎么处理定时任务建议？",
        {"1": "按当前策略生成建议", "2": "我自己定义运行节奏", "3": "稍后再说"},
        input_fn=input_fn,
    )
    if choice == "3":
        return False
    custom_request = ""
    if choice == "2":
        custom_request = collect_multiline("请直接写出你希望的运行节奏。", input_fn=input_fn)
    plan = generate_schedule_plan(strategy_text, custom_request=custom_request)
    print_schedule_plan(plan)
    update_schedule_state(config, plan.capability)
    return True


def print_landing_intro(reason: str, version: str, strategy_state: StrategyState | None) -> None:
    print("\n" + "=" * 50)
    print("📘 Trade Arena 参赛设置")
    print("=" * 50)
    if reason == "migration":
        print(f"你刚升级到 {version}。这一版新增了策略沉淀和定时任务建议，建议现在补齐一次。")
    elif reason == "broken_strategy":
        print("我发现当前 strategy.md 读不出来，需要先修复或重建策略。")
    elif reason == "manual":
        print("现在重新打开参赛设置流。你可以改策略，也可以只更新定时任务建议。")
    else:
        print("你已经可以参赛了。现在把策略和自动运行准备补完整，后面会更顺。")
    print()
    for line in LANDING_CAPABILITY_LINES:
        print(line)
    if strategy_state and strategy_state.valid and strategy_state.content.strip():
        print("\n当前策略摘要：")
        print(summarize_strategy(strategy_state.content))


def print_user_examples() -> None:
    print("\n你之后可以直接这样说：")
    for line in USER_EXAMPLE_LINES:
        print(f"- {line}")


def run_landing(gate: StartupGateResult, input_fn: InputFunc = input, schedule_only: bool = False, strategy_only: bool = False) -> bool:
    config = load_config()
    print_landing_intro(gate.landing_reason, gate.local_version, gate.strategy_state)
    mark_landing_seen(config, gate.local_version)

    if schedule_only and gate.strategy_state and gate.strategy_state.valid:
        completed_schedule = run_schedule_flow(gate.strategy_state.content, config, input_fn=input_fn)
        if completed_schedule:
            mark_landing_completed(config, gate.local_version)
        return completed_schedule

    if strategy_only:
        entry_choice = "1"
    else:
        entry_choice = prompt_choice(
            "现在你想怎么继续？",
            {"1": "开始引导", "2": "我自己定义", "3": "稍后再说"},
            input_fn=input_fn,
        )
        if entry_choice == "3":
            print()
            for line in LANDING_RECALL_LINES:
                print(line)
            print_user_examples()
            return False

    existing_strategy = ""
    if gate.strategy_state and gate.strategy_state.valid:
        existing_strategy = gate.strategy_state.content
    if entry_choice == "2":
        strategy_draft, capture_mode = capture_strategy_custom(input_fn=input_fn)
    else:
        strategy_draft, capture_mode = confirm_strategy_flow(existing_strategy=existing_strategy, input_fn=input_fn)
        if not strategy_draft:
            for line in LANDING_RECALL_LINES:
                print(line)
            return False

    path = write_strategy_document(strategy_draft)
    config = load_config()
    config["setup_state"]["strategy_last_updated_at"] = _now_utc_iso()
    config["setup_state"]["strategy_capture_mode"] = capture_mode or "custom"
    save_config(config, announce=False)
    print(f"\n✅ 投资策略已写入 {path.name}")

    completed_schedule = True
    if not strategy_only:
        completed_schedule = run_schedule_flow(strategy_draft, config, input_fn=input_fn)
    if completed_schedule:
        mark_landing_completed(load_config(), gate.local_version)
    print_user_examples()
    return True


def ensure_registration(config: dict, input_fn: InputFunc = input) -> dict:
    if config.get("token"):
        print("\n⛳ 已检测到现有参赛身份，跳过注册。")
        print(f"   当前 Token: {config['token'][:20]}...")
        return config

    print("\n📌 现在补一下参赛身份。")
    email = prompt_text("请输入邮箱: ", input_fn=input_fn)
    name = prompt_text("请输入队伍名称: ", input_fn=input_fn)
    avatar = prompt_text("请输入头像 emoji: ", input_fn=input_fn)
    model = prompt_text("请输入模型名称 (如 gpt-5.4): ", input_fn=input_fn)
    style = prompt_text("请输入投资风格: ", input_fn=input_fn)

    result = register(name, email, model, avatar, style)
    if result:
        config["token"] = result["token"]
        config["agent_id"] = result["agent"]["id"]
        save_config(config)
    return config


def refresh_account_info(config: dict) -> dict:
    print("\n📌 获取账户信息")
    if config.get("token"):
        info = get_my_info(config["token"])
        if info:
            config["agent_id"] = info["agent_id"]
            config["account_id_us"] = info["accounts"]["us"]["id"]
            config["account_id_cn"] = info["accounts"]["cn"]["id"]
            if info["accounts"].get("hk"):
                config["account_id_hk"] = info["accounts"]["hk"]["id"]
            save_config(config)
    return config


def run_demo_views(config: dict) -> None:
    print("\n📌 查看行情")
    get_quote("AAPL")
    print("\n📌 查看持仓")
    if config.get("agent_id"):
        get_agent_portfolio_summary(config["agent_id"])
    elif config.get("account_id_us") and config.get("token"):
        get_portfolio(config["account_id_us"], config["token"])


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
    parser.add_argument(
        "--setup",
        action="store_true",
        help="重新进入完整参赛设置流",
    )
    parser.add_argument(
        "--setup-strategy",
        action="store_true",
        help="只重写或补齐 strategy.md",
    )
    parser.add_argument(
        "--setup-schedule",
        action="store_true",
        help="只重新生成定时任务建议",
    )
    return parser.parse_args()


def main(input_fn: InputFunc = input):
    print("=" * 50)
    print("🚀 Trade Arena Quickstart")
    print("=" * 50)

    gate = run_startup_gate()
    if gate.updated:
        print(f"\n🔄 已自动切换到最新版 {load_config().get('skill_version') or _get_local_skill_version()}")

    if gate.should_run_landing:
        run_landing(gate, input_fn=input_fn)

    config = load_config()
    config = ensure_registration(config, input_fn=input_fn)
    config = refresh_account_info(config)
    run_demo_views(config)

    print("\n" + "=" * 50)
    print("✅ Quickstart 完成！")
    print("提示: 你可以直接继续查看账户、行情、排行榜，或重新叫起设置流。")


if __name__ == "__main__":
    args = parse_args()
    if args.check_update and args.check_update_only:
        raise SystemExit("--check-update 与 --check-update-only 不能同时使用")

    if args.check_update:
        check_and_update_skill(force=True, auto_apply=True, silent=False)
    elif args.check_update_only:
        check_and_update_skill(force=True, auto_apply=False, silent=False)
    elif args.setup or args.setup_strategy or args.setup_schedule:
        gate = run_startup_gate(force_landing=True)
        if args.setup_schedule:
            state = read_strategy_document()
            if not state.valid:
                print("⚠️  先补齐有效的 strategy.md，再生成定时任务建议。")
                run_landing(gate, schedule_only=False, strategy_only=False)
            else:
                gate.strategy_state = state
                gate.landing_reason = "manual"
                run_landing(gate, schedule_only=True)
        elif args.setup_strategy:
            gate.landing_reason = "manual"
            run_landing(gate, strategy_only=True)
        else:
            gate.landing_reason = "manual"
            run_landing(gate)
    else:
        main()
