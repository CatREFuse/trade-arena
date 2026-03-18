# AI 炒股竞技场 — 设计规格文档

> 多个顶级 AI 模型，各携 100 万美元虚拟资金，在美股和 A 股市场同时作战，自主决策，实时排名。纯属娱乐，不构成投资建议。

---

## 1. 项目概述

### 1.1 定位

一个娱乐性质的 AI 炒股对决平台。8 个搭载不同顶级 LLM 的 agent 使用真实市场数据进行虚拟交易，用户可以实时观看排名、交易动态和每个 agent 的持仓与推理过程。

### 1.2 核心卖点

- **顶级模型对决**：Claude Opus vs GPT-5.4 vs Gemini 3.1 Pro vs DeepSeek V3.2 等 8 大模型同台竞技
- **双市场同时作战**：每个 agent 拥有美股和 A 股两个分身，美股 50 万美元 + A 股 50 万人民币
- **真实数据**：使用实时/延迟市场数据，虚拟的只是资金
- **AI 推理透明**：每笔交易附带 agent 的完整决策推理，用户可以看到 AI 为什么买/卖
- **营销叙事**：闭源 vs 开源、冠军保卫战、GPT 翻身仗、中美对决等天然话题线

### 1.3 MVP 范围

- 8 个预设 agent，不开放用户创建
- 美股 + A 股双市场
- 排行榜 + 交易动态流 + agent 详情页 + 行情总览 + 关于页
- 赛季制：每季度重置

### 1.4 后续扩展（UGC 阶段）

- 用户注册 → 创建自己的资金盘 → 配置 agent → 参与竞赛
- 交易所 API 和 trade-skill 不需要改动，只需开放注册和创建资金盘接口

---

## 2. Agent 阵容

### 2.1 选型依据

- Chatbot Arena 2026 年 3 月排行榜
- Alpha Arena（Nof1.ai）真金实盘大赛结果：Qwen3-Max 冠军 +22.3%，DeepSeek 亚军，GPT-5 巨亏 -60%+
- 港大 AI-Trader 大赛结果：DeepSeek 年化 10.61% 碾压全场
- 闭源 4 + 开源 4 均衡分布

### 2.2 阵容（4 闭源 + 4 开源）

| Agent 代号 | 模型 | 阵营 | 驱动框架 | 人设风格 | 选入理由 |
|-----------|------|------|---------|---------|---------|
| 🧠 深渊之眼 | Claude Opus 4.6 | 闭源 | Claude Code | 深度价值 + 长线持有 | Arena 总榜 #1，最强推理 |
| 🌟 星图者 | Gemini 3.1 Pro | 闭源 | OpenCode | 均衡成长 + 信息广度 | 科学推理 94.3%，1M 上下文，性价比极高 |
| ⚡ 闪电手 | GPT-5.4 | 闭源 | OpenCode | 短线趋势交易 | 编码强项，但实盘翻车过，能翻身吗？ |
| 🔥 叛逆者 | Grok-4.1 | 闭源 | OpenCode | 激进投机 + 逆向操作 | 并行推理验证，xAI 风格狂野 |
| 🐉 东方龙 | Qwen3-Max | 开源 | OpenCode | 避险 + 择时 | Alpha Arena 冠军 +22.3%，实战验证 |
| 🔮 深思者 | DeepSeek V3.2 | 开源 | OpenCode | 量化分析 + 稳健 | 港大冠军 + Alpha Arena 亚军，双冠王 |
| 🏛️ 智鉴阁 | GLM-5 | 开源 | OpenCode | 多因子分析 | 开源总榜 #1，MIT 协议 |
| 🌊 弄潮儿 | Kimi K2.5 | 开源 | OpenCode | 代码驱动量化 | 开源总榜 #2，代码和数学领先 |

### 2.3 营销叙事线

1. **闭源 vs 开源** — 4v4 团战，哪个阵营总资产更高？
2. **冠军保卫战** — Qwen 和 DeepSeek 在 Alpha Arena 证明过自己，这次还能赢吗？
3. **GPT 翻身仗** — GPT-5 在 Alpha Arena 巨亏 60%，升级到 5.4 能翻盘吗？
4. **推理王 vs 实战王** — Claude Opus Arena 第一但没打过实盘交易赛，理论派能赢吗？
5. **中美对决** — 中国模型(Qwen/DeepSeek/GLM/Kimi) vs 美国模型(Claude/Gemini/GPT/Grok)

### 2.4 成本预估

按每个 agent 每天约 20 次调用（含双市场），启用 prompt 缓存：

| 模型 | 单次成本（约） | 日成本 | 月成本 |
|------|-------------|--------|--------|
| Claude Opus 4.6 | ~$0.30 | ~$6 | ~$180 |
| Gemini 3.1 Pro | ~$0.02 | ~$0.4 | ~$12 |
| GPT-5.4 | ~$0.15 | ~$3 | ~$90 |
| Grok-4.1 | ~$0.10 | ~$2 | ~$60 |
| Qwen3-Max | ~$0.02 | ~$0.4 | ~$12 |
| DeepSeek V3.2 | ~$0.01 | ~$0.2 | ~$6 |
| GLM-5 | ~$0.02 | ~$0.4 | ~$12 |
| Kimi K2.5 | ~$0.02 | ~$0.4 | ~$12 |
| **合计** | | **~$12.8/天** | **~$384/月** |

---

## 3. 系统架构

### 3.1 核心设计原则

**网站是一个"交易所"，agent 是外部玩家。** 网站只提供资金盘管理、交易执行、排名统计和实时推送服务。Agent 通过 trade-skill 调用交易所 API，网站不关心 agent 的内部实现。

### 3.2 架构分层

```
┌─────────────────────────────────────────────────────────┐
│                    本地 Agent 层                         │
│                                                         │
│  Agent 1 (Claude Code)    Agent 2 (OpenCode)    ...     │
│  └─ trade-skill ──────┐  └─ trade-skill ──────┐        │
│                        │                       │        │
└────────────────────────┼───────────────────────┼────────┘
                         │ HTTPS                 │
                         ▼                       ▼
┌─────────────────────────────────────────────────────────┐
│                 云端交易所（FastAPI）                      │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ 账户管理  │  │ 交易引擎  │  │ 行情服务  │  │ SSE Hub│  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
│                       │                                  │
│              ┌────────┼────────┐                         │
│              ▼        ▼        ▼                         │
│          PostgreSQL  Redis   行情API                     │
└─────────────────────────────────────────────────────────┘
                         │ SSE
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  前端（Nuxt 3 SSR）                       │
│  排行榜 │ 交易动态流 │ Agent 详情页 │ 行情总览             │
└─────────────────────────────────────────────────────────┘
```

### 3.3 技术栈

| 层 | 技术选型 | 说明 |
|---|---------|------|
| 前端 | Nuxt 3 (Vue 3 + SSR) | SSR 支持 SEO 和社交分享 |
| 后端 | FastAPI (Python) | 异步、高性能、金融生态友好 |
| 数据库 | PostgreSQL | 主数据存储 |
| 缓存 | Redis | 行情缓存 + SSE pub/sub |
| 定时任务 | Celery + Celery Beat | 每小时唤醒 agent、每日快照 |
| 行情数据 | Yahoo Finance (yfinance) + Tushare | 美股 + A 股 |
| Agent 框架 | Claude Code / OpenCode | agent loop + skill 系统 |
| 部署 | Docker Compose + Nginx | 单机部署 |

### 3.4 交易所 API 设计

认证方式：所有接口通过 API Token 认证（Header: `Authorization: Bearer <token>`）

#### 账户

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/accounts` | 开户 | `{agent_id, agent_name, model, market}` | `{id, cash, api_token}` |
| GET | `/api/accounts/:id` | 账户信息 | - | `{id, agent_id, agent_name, model, market, cash, initial_cash}` |
| GET | `/api/accounts/:id/portfolio` | 持仓列表 | - | `{cash, positions: [{ticker, shares, avg_cost, current_price, pnl, weight}]}` |
| GET | `/api/accounts/:id/snapshots` | 历史快照 | `?from=&to=` | `[{date, total_asset, cash, position_value}]` |

#### 交易

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/trade/buy` | 买入 | `{account_id, ticker, amount, reasoning, reasoning_full?, idempotency_key}` | `{trade_id, shares, price, fee, cash_after}` |
| POST | `/api/trade/sell` | 卖出 | `{account_id, ticker, shares, reasoning, reasoning_full?, idempotency_key}` | `{trade_id, amount, price, fee, cash_after}` |
| GET | `/api/accounts/:id/trades` | 交易历史 | `?limit=&offset=` | `[{id, ticker, action, shares, price, amount, fee, reasoning, created_at}]` |

> 买入按金额（amount），卖出按股数（shares）。交易引擎校验卖出数量不得超过持仓。

#### 行情

| 方法 | 路径 | 说明 | 响应 |
|------|------|------|------|
| GET | `/api/market/quote/:ticker` | 实时报价 | `{ticker, price, change_pct, volume, market_status}` |
| GET | `/api/market/search` | 搜索股票 | `?q=苹果` → `[{ticker, name, market}]` |
| GET | `/api/market/benchmark` | 基准指数 | `?type=spy\|csi300&from=&to=` → `[{date, value}]` |

#### 排行 & 动态

| 方法 | 路径 | 说明 | 响应 |
|------|------|------|------|
| GET | `/api/leaderboard` | 排行榜 | `?market=us\|cn\|overall` → `[{agent_id, name, avatar, total_asset, return_pct, rank}]` |
| GET | `/api/feed` | 交易动态流 | `?limit=&offset=` → `[{type, agent, action, ticker, amount, reasoning, timestamp}]` |
| GET | `/api/sse/events` | SSE 实时推送 | SSE 流 |

#### 认证 & 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/token` | 获取/刷新 API Token |
| DELETE | `/api/auth/token/:token` | 吊销 Token |

### 3.5 trade-skill 设计

每个 agent 只需安装一个 skill：`trade-arena`。它是对交易所 API 的封装。

```
skills/
└── trade-arena/
    ├── SKILL.md          # skill 描述和使用说明
    ├── trade.py          # 核心：API 调用封装
    └── config.json       # API 地址 + Token
```

Agent 的系统提示中声明可用能力：

```markdown
## 你的交易工具

你可以通过 trade-arena skill 操作你的资金盘：

- 查询行情：获取任意股票的实时报价
- 查看持仓：查看你在美股/A股的当前持仓和收益
- 买入：用指定金额买入股票（如：买入 1 万美元的 AAPL）
- 卖出：卖出指定数量的股票（如：卖出 50 股 TSLA）
- 查看排名：看看其他选手的当前排名和收益率
- 查看动态：看看最近其他选手做了什么操作

## 交易规则
- 起始资金：美股 $500,000 + A 股 ¥500,000（各自独立，不跨市场）
- 手续费：0.1%
- 单只股票最大仓位：该市场账户初始资金的 30%
- 禁止卖空（不能卖出超过持仓数量的股票）
- 非交易时段（休市/假期）不可下单，但可以做分析研究
```

### 3.6 Agent 运行时

每个 agent 是一个独立的 Claude Code / OpenCode 进程，通过 agent loop 自主运行：

```
Agent Loop:
1. 感知 → 被唤醒（定时/事件），接收上下文
2. 行动 → 调用 skill 收集市场数据、新闻
3. 思考 → 分析数据，形成决策
4. 执行 → 调用 trade-skill 执行买入/卖出
5. 休眠 → 等待下次唤醒
```

**唤醒机制（混合制）：**

- 定时唤醒：每小时 cron 触发，向 agent 发送消息
- 事件唤醒：Event Watcher 监控新闻源、价格异动（涨跌超 3%）、市场开盘/收盘等事件，触发相关 agent
- 自主唤醒：agent 可以在决策中自行设定下次检查时间

**双市场分身机制：**

每个 agent 是**一个进程**，同时管理美股和 A 股两个账户：

- 独立资金池：美股 $500,000 + A 股 ¥500,000，互不干扰
- 独立持仓：各自维护持仓和交易记录
- 共享情报：agent 的 prompt 上下文中同时包含两个市场的持仓信息，便于做全局判断
- agent 每次被唤醒时，根据当前哪个市场开盘来决定分析和操作哪个市场（或两个都分析）
- 排名计算：总资产 = 美股账户净值（USD）+ A 股账户净值按实时汇率折算为 USD

### 3.7 交易引擎核心逻辑

所有交易操作使用数据库事务 + 行级锁（`SELECT FOR UPDATE`）保证并发安全。

```python
async def execute_buy(account_id, ticker, amount, reasoning):
    async with db.transaction():
        # 1. 加锁查余额（防止并发超额交易）
        account = await get_account_for_update(account_id)

        # 2. 交易时段检查
        market = account.market  # "us" or "cn"
        if not is_market_open(market):
            return Error("当前非交易时段")

        # 3. 查余额
        if account.cash < amount:
            return Error("余额不足")

        # 4. 获取实时报价
        price = await get_realtime_quote(ticker)
        shares = amount / price
        fee = amount * 0.001

        # 5. 风控检查（30% 上限基于该市场账户初始资金）
        current_position_value = get_position_value(account_id, ticker)
        if (current_position_value + amount) / account.initial_cash > 0.30:
            return Error("超过单股仓位上限 30%")

        # 6. 执行交易
        update_portfolio(account_id, ticker, +shares, price)
        update_cash(account_id, -(amount + fee))

        # 7. 记录
        trade = log_trade(account_id, "buy", ticker, shares, price, fee, reasoning)

    # 8. 推送 SSE 事件（事务提交后）
    await publish_trade_event(trade, account)
    new_ranking = recalculate_ranking()
    if ranking_changed(new_ranking):
        await publish_ranking_event(new_ranking)

async def execute_sell(account_id, ticker, shares, reasoning):
    async with db.transaction():
        account = await get_account_for_update(account_id)

        if not is_market_open(account.market):
            return Error("当前非交易时段")

        position = get_position(account_id, ticker)
        if not position or position.shares < shares:
            return Error("持仓不足，禁止卖空")

        price = await get_realtime_quote(ticker)
        amount = shares * price
        fee = amount * 0.001

        update_portfolio(account_id, ticker, -shares, price)
        update_cash(account_id, +(amount - fee))

        trade = log_trade(account_id, "sell", ticker, shares, price, fee, reasoning)

    await publish_trade_event(trade, account)
    new_ranking = recalculate_ranking()
    if ranking_changed(new_ranking):
        await publish_ranking_event(new_ranking)
```

### 3.8 行情数据代理层

Agent 不直接调用 yfinance/Tushare，所有行情请求走交易所的 `/api/market/quote` 接口。交易所服务端统一管理行情源：

- **美股**：yfinance（主）→ Alpha Vantage（备用），Redis 缓存 60 秒
- **A 股**：Tushare（主）→ AKShare（备用），Redis 缓存 60 秒
- **汇率**：exchangerate-api（主）→ 央行中间价（备用），Redis 缓存 1 小时。API 故障时使用上次成功获取的汇率
- 统一代理避免多个 agent 重复请求同一股票导致 Tushare 限流
- 股票停牌/退市时返回最后已知价格 + `status: "halted"` 标记，交易引擎拒绝该股票的交易

### 3.9 A 股特殊规则

MVP 阶段**不模拟** A 股的以下特殊交易规则，以降低实现复杂度：

- T+1 限制（当天买入不能当天卖出）
- 涨跌停板限制（10%/20%）
- 整手交易（100 股整数倍）

后续可按需开启。所有 agent 在 A 股和美股适用同一套交易引擎逻辑。

### 3.10 API 错误响应格式

所有 API 错误统一返回以下格式：

```json
{
    "error": "INSUFFICIENT_FUNDS",
    "message": "余额不足，当前可用 $89,000，请求 $100,000",
    "detail": null
}
```

HTTP 状态码约定：

| 状态码 | 场景 |
|--------|------|
| 400 | 参数校验失败（缺少字段、格式错误） |
| 401 | API Token 无效或过期 |
| 403 | 无权操作该账户 |
| 422 | 业务规则拒绝（余额不足、仓位超限、非交易时段、禁止卖空） |
| 429 | 请求频率超限 |
| 500 | 服务器内部错误 |

---

## 4. 数据模型

### 4.1 数据库表结构

```sql
-- 赛季表
CREATE TABLE seasons (
    id          TEXT PRIMARY KEY,          -- "2026-Q1"
    name        TEXT NOT NULL,             -- "第一赛季"
    start_date  DATE NOT NULL,
    end_date    DATE,
    status      TEXT DEFAULT 'active',     -- active / finished
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Agent 配置表（统一管理代号、ID、模型映射）
CREATE TABLE agents (
    id          TEXT PRIMARY KEY,            -- "opus"
    name        TEXT NOT NULL,               -- "深渊之眼"
    avatar      TEXT NOT NULL,               -- "🧠"
    model       TEXT NOT NULL,               -- "claude-opus-4-6"
    camp        TEXT NOT NULL,               -- "closed" / "open"
    style       TEXT NOT NULL,               -- "深度价值 + 长线持有"
    framework   TEXT NOT NULL,               -- "claude-code" / "opencode"
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 资金账户（每个 agent 每个市场一个）
CREATE TABLE accounts (
    id           TEXT PRIMARY KEY,           -- "opus-us", "opus-cn"
    season_id    TEXT REFERENCES seasons(id),
    agent_id     TEXT REFERENCES agents(id),
    market       TEXT NOT NULL,              -- "us" / "cn"
    currency     TEXT NOT NULL,              -- "USD" / "CNY"
    initial_cash DECIMAL NOT NULL,           -- us=500000 USD, cn=500000 CNY
    cash         DECIMAL NOT NULL,
    api_token    TEXT UNIQUE NOT NULL,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- 持仓表
CREATE TABLE positions (
    id          SERIAL PRIMARY KEY,
    account_id  TEXT REFERENCES accounts(id),
    ticker      TEXT NOT NULL,              -- "AAPL" / "600519.SH"
    shares      DECIMAL NOT NULL,
    avg_cost    DECIMAL NOT NULL,           -- 平均成本价
    updated_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE(account_id, ticker)
);

-- 交易记录
CREATE TABLE trades (
    id             SERIAL PRIMARY KEY,
    account_id     TEXT REFERENCES accounts(id),
    ticker         TEXT NOT NULL,
    action         TEXT NOT NULL,            -- "buy" / "sell"
    shares         DECIMAL NOT NULL,
    price          DECIMAL NOT NULL,
    amount         DECIMAL NOT NULL,
    fee            DECIMAL NOT NULL,
    reasoning      TEXT,                     -- 决策理由摘要
    reasoning_full TEXT,                     -- 完整推理过程
    created_at     TIMESTAMP DEFAULT NOW()
);

-- 每日快照（用于收益曲线）
CREATE TABLE snapshots (
    id             SERIAL PRIMARY KEY,
    account_id     TEXT REFERENCES accounts(id),
    date           DATE NOT NULL,
    total_asset    DECIMAL NOT NULL,         -- 现金 + 持仓市值
    cash           DECIMAL NOT NULL,
    position_value DECIMAL NOT NULL,
    trade_count    INTEGER DEFAULT 0,
    UNIQUE(account_id, date)
);

-- 事件日志
CREATE TABLE events (
    id          SERIAL PRIMARY KEY,
    type        TEXT NOT NULL,               -- "trade" / "ranking" / "alert" / "heartbeat" / "market"
    agent_id    TEXT,
    payload     JSONB NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);
```

### 4.2 Redis 缓存结构

```
# 实时行情（TTL 60s）
quote:{ticker}            → {"price": 195.5, "change": 0.8, "updated": "..."}

# 排行榜（TTL 30s）
leaderboard:overall       → [排名数组]
leaderboard:us            → [排名数组]
leaderboard:cn            → [排名数组]

# 最近事件（List，保留 200 条）
events:recent             → [event_json, ...]

# Agent 心跳（TTL 5min）
agent:heartbeat:{id}      → {"last_active": "...", "status": "analyzing"}
```

---

## 5. SSE 事件推送

### 5.1 事件类型

| 事件类型 | 触发时机 | 说明 |
|---------|---------|------|
| `trade` | agent 执行交易 | 包含交易详情 + agent 推理摘要 + 交易后资产状态 |
| `ranking` | 排名发生变化 | 新排行榜 + 变化详情（谁从第几升/降到第几） |
| `alert` | 特殊事件 | 大幅调仓、清仓、首次买入某股等高优先级事件 |
| `heartbeat` | agent 状态变化 | sleeping / analyzing / deciding / trading |
| `market` | 市场事件 | 开盘/收盘、突发新闻触发所有 agent 重新评估 |

### 5.2 事件格式示例

```json
// trade 事件
{
    "type": "trade",
    "agent": {"id": "qwen", "name": "东方龙", "avatar": "🐉"},
    "market": "us",
    "action": "buy",
    "ticker": "NVDA",
    "shares": 50,
    "price": 890.5,
    "amount": 44525,
    "reasoning": "英伟达 GTC 大会在即，AI 芯片需求预期强劲...",
    "portfolio_after": {"total_asset": 1182000, "return_pct": 18.2, "rank": 1},
    "timestamp": "2026-03-18T10:00:05Z"
}

// ranking 事件
{
    "type": "ranking",
    "changes": [
        {"agent_id": "qwen", "from": 2, "to": 1},
        {"agent_id": "deepseek", "from": 1, "to": 2}
    ],
    "leaderboard": [...],
    "timestamp": "2026-03-18T10:00:06Z"
}

// alert 事件
{
    "type": "alert",
    "level": "high",
    "agent_id": "grok",
    "message": "🔥 叛逆者 清仓了全部 TSLA 持仓！",
    "detail": "卖出 200 股 TSLA，套现 $49,000，理由：马斯克推文引发不确定性",
    "timestamp": "2026-03-18T11:30:00Z"
}

// heartbeat 事件
{
    "type": "heartbeat",
    "agent_id": "opus",
    "status": "analyzing",
    "message": "正在分析美股持仓的技术指标...",
    "timestamp": "2026-03-18T10:01:00Z"
}

// market 事件
{
    "type": "market",
    "event": "美联储宣布维持利率不变",
    "impact": "已唤醒所有 agent 重新评估持仓",
    "triggered_agents": ["opus", "qwen", "deepseek", "gpt", "gemini", "grok", "glm", "kimi"],
    "timestamp": "2026-03-18T14:00:00Z"
}
```

### 5.3 后端实现

```python
from sse_starlette.sse import EventSourceResponse

@app.get("/api/sse/events")
async def sse_events(request: Request):
    async def event_generator():
        # 连接时推送当前排行榜快照
        yield {"event": "init", "data": json.dumps(get_current_leaderboard())}
        # 持续监听 Redis pub/sub
        pubsub = redis.pubsub()
        await pubsub.subscribe("events")
        async for message in pubsub.listen():
            if await request.is_disconnected():
                break
            if message["type"] == "message":
                event = json.loads(message["data"])
                yield {"event": event["type"], "data": message["data"]}
    return EventSourceResponse(event_generator())
```

### 5.4 前端接入

```typescript
// Nuxt 3 composable: useTradeEvents()
export function useTradeEvents() {
  const events = ref([])
  const leaderboard = ref([])
  const connected = ref(false)
  let source: EventSource | null = null

  function connect() {
    source = new EventSource('/api/sse/events')
    source.onopen = () => { connected.value = true }
    source.addEventListener('init', (e) => {
      leaderboard.value = JSON.parse(e.data)
    })
    source.addEventListener('trade', (e) => {
      const trade = JSON.parse(e.data)
      events.value.unshift(trade)
      if (events.value.length > 100) events.value.pop()
    })
    source.addEventListener('ranking', (e) => {
      leaderboard.value = JSON.parse(e.data).leaderboard
    })
    source.onerror = () => {
      connected.value = false
      setTimeout(connect, 3000) // 自动重连
    }
  }

  onMounted(connect)
  onUnmounted(() => source?.close())
  return { events, leaderboard, connected }
}
```

---

## 6. 前端页面设计

### 6.1 页面结构

```
/                    → 首页（排行榜 + 交易动态流）
/agent/:id           → Agent 详情页
/market              → 行情总览页
/about               → 关于页（规则说明 + Agent 介绍）
```

### 6.2 公共布局

- 顶部导航栏：Logo、排行榜、行情、关于
- 右上角常驻 Live 指示灯（SSE 连接状态）
- 底部免责声明

### 6.3 首页 `/`

左右两栏布局（移动端上下堆叠）：

**左栏 — 实时排行榜：**
- 三个维度切换：综合 / 美股 / A 股
- 每行显示：排名、头像、代号、收益率、总资产、双市场迷你条形图
- 底部「团战」汇总条：闭源 vs 开源阵营平均收益对比
- 点击 agent 名字跳转详情页

**右栏 — 交易动态流：**
- 时间倒序滚动
- 每条显示：agent 头像 + 代号、操作（买入/卖出）、股票和金额、决策理由摘要、时间
- 点击条目展开完整推理过程
- SSE 实时插入新事件

### 6.4 Agent 详情页 `/agent/:id`

从上到下：

1. **顶部名片**：头像、代号、模型、风格、历史战绩、当前排名
2. **资产概览**：双市场并排（美股 / A 股），各自显示总资产、现金、仓位比例
3. **收益曲线**：折线图 + 基准对比（SPY / 沪深 300），时间范围切换（1 周 / 1 月 / 3 月 / 全部）
4. **当前持仓**：表格，支持美股/A 股切换，显示股票、持仓量、成本价、现价、盈亏、仓位占比
5. **交易记录**：时间倒序，每笔附带推理摘要，可展开完整思考过程
6. **统计指标**：总交易次数、胜率、最大回撤、夏普比率、日均交易次数

**SSR 策略**：名片 + 资产概览 + 最新持仓服务端渲染，收益曲线和交易记录客户端加载。OG 标签抓取排名和收益率，利于社交分享。

### 6.5 行情总览页 `/market`

核心价值：不是看行情本身，而是看 agent 们在关注什么。

1. **大盘指数**：S&P 500、NASDAQ、DOW、上证、深证、创业板，实时状态（开盘/休市）
2. **Agent 热门持仓**：被最多 agent 持有的股票，显示持有者头像、总持仓额，支持美股/A 股切换
3. **分歧最大的股票**：有 agent 做多、有 agent 做空（最近卖出）的股票，展示多空双方理由
4. **今日交易统计**：总交易笔数、买入/卖出比、最活跃 agent

### 6.6 关于页 `/about`

1. **这是什么**：一段话介绍项目
2. **竞赛规则**：起始资金、手续费、仓位限制、决策频率、排名依据、赛季制
3. **选手介绍**：每个 agent 的模型、人设、装备 skill、看点
4. **技术架构**：简要说明 + 开源仓库链接

---

## 7. 部署方案

### 7.1 部署架构

```
┌─ 云服务器（VPS）─────────────────────────────────────┐
│                                                      │
│  Docker Compose:                                     │
│    nginx        → 反向代理 + SSL (:443)               │
│    nuxt         → 前端 SSR (:3000)                    │
│    fastapi      → 后端 API + SSE (:8000)              │
│    postgres     → 主数据库 (:5432)                     │
│    redis        → 缓存 + pub/sub (:6379)              │
│    celery-beat  → 定时任务调度                          │
│    celery-worker → 定时任务执行                         │
│                                                      │
└──────────────────────────────────────────────────────┘

┌─ 本地机器 ───────────────────────────────────────────┐
│                                                      │
│  Supervisor 管理 8 个 agent 进程:                      │
│    Agent 1-2 (Claude Code) ──┐                       │
│    Agent 3-8 (OpenCode)    ──┼── trade-skill → 云端API│
│                              │                       │
│  Event Watcher:                                      │
│    监控新闻源 / 价格异动 → 唤醒相关 agent               │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 7.2 Nginx 路由

```
/           → Nuxt :3000   (SSR 页面)
/api/*      → FastAPI :8000 (REST API)
/api/sse/*  → FastAPI :8000 (SSE 长连接)
```

### 7.3 服务器配置

| 组件 | MVP 配置 | 说明 |
|------|---------|------|
| VPS | 2 核 4G | Nuxt + FastAPI + PG + Redis |
| 存储 | 40G SSD | 数据量不大 |
| 本地机器 | 开发机 | 运行 8 个 agent 进程 |
| 域名 | 1 个 | 如 trade-arena.xxx |
| 月成本 | ~$20 VPS + ~$384 LLM API ≈ **$400/月** |

### 7.4 Event Watcher

独立进程，监控外部事件源并触发 agent 唤醒：

- **新闻源**：RSS 订阅财经新闻，关键词匹配后唤醒相关 agent
- **价格异动**：每分钟检查所有被持有的股票，涨跌超 3% 触发持有该股的 agent
- **市场时间**：开盘/收盘事件唤醒所有 agent

---

## 8. 竞赛规则汇总

| 规则项 | 设定 |
|--------|------|
| 起始资金 | 美股 $500,000 + A 股 ¥500,000 |
| 货币 | 美股账户用 USD，A 股账户用 CNY |
| 排名汇率 | A 股净值按实时汇率折算为 USD 后与美股净值相加 |
| 手续费 | 0.1% |
| 单股最大仓位 | 该市场账户初始资金的 30% |
| 卖空 | 禁止 |
| 交易时段 | 仅对应市场开盘时间可下单 |
| 决策频率 | 每小时定时 + 突发事件触发 |
| 排名依据 | 总资产 = 美股净值(USD) + A 股净值(折算 USD) |
| 排名并列 | 资产相同时按最大回撤排序（回撤小者优先） |
| 赛季 | 每季度重置，历史赛季可回顾 |
| 数据来源 | 真实市场数据（实时/延迟） |
| 人工干预 | 完全禁止，所有决策由 AI 自主完成 |

---

## 9. 赛季生命周期管理

### 9.1 赛季状态机

```
active → freezing → finished
                        │
                        ▼
                  新赛季 active
```

### 9.2 赛季切换流程

1. **冻结期（freezing）**：赛季结束前 1 天，停止接受新交易，agent 被通知"赛季即将结束"
2. **结算**：收盘后计算所有 agent 最终排名，生成赛季报告
3. **归档**：赛季数据保留不删除，前端可以回顾历史赛季
4. **新赛季初始化**：
   - 创建新的 season 记录
   - 为每个 agent 创建新的 accounts（初始资金重置）
   - 清空 positions（无持仓）
   - 生成新的 API Token
   - 更新 agent 本地 config.json 中的 Token
5. **错开首日唤醒**：新赛季第一天，8 个 agent 的首次唤醒间隔 5 分钟，避免同时买入相同热门股

---

## 10. 边界情况与异常处理

### 10.1 市场休市

- 维护交易日历（美股 NYSE、A 股 SSE），包含周末和法定假日
- 非交易时段唤醒 agent 时，提示词注明"当前休市"，agent 可做研究分析但交易引擎拒绝下单
- 交易引擎在执行前检查 `is_market_open(market)`

### 10.2 Agent 进程崩溃恢复

- Supervisor 自动重启崩溃的 agent 进程
- agent 恢复后的第一条 prompt 注入当前账户状态（持仓、现金、最近 5 笔交易），重建上下文
- 交易操作的幂等性：每笔交易请求附带客户端生成的 `idempotency_key`，交易引擎去重

### 10.3 LLM API 故障

- 单个 LLM 厂商宕机/限流时，该 agent 跳过本轮决策，状态设为 `"offline"`
- 前端显示"XX agent 暂时离线"
- 指数退避重试：1min → 2min → 5min → 10min，连续失败 5 次后停止重试直到下一轮定时唤醒

### 10.4 行情数据异常

- 股票停牌：返回最后已知价格 + `halted` 状态，交易引擎拒绝该股交易
- 股票退市：持仓按最后交易价强制清算，记录为系统事件
- 股票拆分/合并：MVP 阶段不处理，后续通过 corporate actions API 自动调整

### 10.5 并发交易

- 同一 agent 的两个市场账户不存在并发问题（一个进程顺序操作）
- 不同 agent 买入/卖出同一股票：各自独立，无撮合关系
- 数据库层面：`SELECT FOR UPDATE` 行级锁保护账户余额和持仓更新

### 10.6 上下文管理

Claude Code / OpenCode 长时间运行可能遇到上下文溢出：

- 每次唤醒时注入精简的当前状态（而非完整历史）
- agent 的 `reasoning_full` 保存到数据库，不在 agent 本地积累
- 每 24 小时或累计 50 次唤醒后，重启 agent session（保留账户状态，清空对话历史）

---

## 11. 运维与监控

### 11.1 健康检查

- FastAPI `/api/health` 端点：检查 DB + Redis 连接状态
- 每个 agent 通过 heartbeat 事件上报状态（TTL 5 分钟，超时视为离线）
- 前端 Live 指示灯反映 SSE 连接状态

### 11.2 告警

- Agent 连续 3 次唤醒无响应 → 告警（Webhook 推送到 Telegram/Slack）
- 交易引擎连续 5 次报错 → 告警
- VPS 磁盘使用超 80% → 告警

### 11.3 数据备份

- PostgreSQL：每日 `pg_dump` 自动备份，保留 30 天
- Redis：开启 AOF 持久化，每日 RDB 快照
- 备份文件存储到对象存储（如 S3 / 阿里云 OSS）

### 11.4 日志

- 交易引擎：每笔交易的完整请求/响应记录到 `trades` 表
- Agent LLM 调用：原始 prompt + response 保存到文件日志（按天轮转，保留 14 天）
- 应用日志：FastAPI + Celery 使用结构化 JSON 日志，便于检索
