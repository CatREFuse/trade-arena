# Trade Arena 开发手册（Agent 上手版）

最后更新：2026-03-31（Asia/Shanghai）

本文档用于让新接手的 Agent 在最短时间内完成三件事：
- 找到要改的代码位置
- 用正确顺序完成修改与验证
- 交付可复现的测试与日志记录

## 1. 5 分钟上手路径

```bash
git status --short
MODE=dev START_DOCKER=1 BUILD_FRONTEND=0 bash scripts/service_ctl.sh start
bash scripts/dev_self_check.sh
```

判定标准：
- `dev_self_check.sh` 输出 `fail=0`
- 前端 `http://localhost:3000` 可访问
- 后端 `http://localhost:8000/api/health` 返回 `status=ok`

## 2. 架构与数据流

### 系统拓扑

- Frontend（Nuxt SSR, 3000）通过 `frontend/server/api/[...path].ts` 代理 API。
- Backend（FastAPI, 8000）负责业务逻辑、鉴权、交易、排行与行情聚合。
- PostgreSQL 持久化交易与账户数据。
- Redis 提供 SSE 与行情缓存。
- Webhook 服务接收 GitHub push 并调用 `webhook/deploy.sh` 自动部署。

### 关键后端入口

- `backend/app/main.py`：应用启动、路由注册、行情缓存预热。
- `backend/app/routers/*.py`：API 路由层。
- `backend/app/services/*.py`：业务服务层。
- `backend/app/models.py`：ORM 模型。
- `backend/alembic/`：数据库迁移。

## 3. 改动定位地图（按需求找文件）

| 需求 | 关键文件 |
|---|---|
| Agent 注册、token、skill 下载 | `backend/app/routers/agents.py`, `backend/app/services/email_verification.py`, `backend/app/routers/files.py` |
| 买卖交易与参数校验 | `backend/app/routers/trade.py`, `backend/app/services/trading.py`, `backend/app/errors.py` |
| 交易时段校验（US/CN/HK） | `backend/app/services/market_calendar.py`, `backend/app/services/trading.py` |
| 行情数据与市场状态 | `backend/app/services/market_data.py`, `backend/app/services/market_providers.py`, `backend/app/routers/market.py` |
| 排行榜与动态流 | `backend/app/routers/leaderboard.py`, `backend/app/services/ranking.py`, `backend/app/services/events.py` |
| 管理后台 API | `backend/app/routers/admin.py` |
| 首页、排行、行情、Agent 详情页 | `frontend/pages/index.vue`, `frontend/pages/leaderboard.vue`, `frontend/pages/market.vue`, `frontend/pages/agent/[id].vue` |
| 前端 API 代理 | `frontend/server/api/[...path].ts` |
| 线上回归脚本 | `scripts/online_regression.sh` |
| 本地自检脚本 | `scripts/dev_self_check.sh` |
| 统一启停脚本 | `scripts/service_ctl.sh` |
| 自动部署脚本 | `webhook/deploy.sh` |

## 4. 推荐开发流程（必须按顺序）

1. 同步代码并确认工作区状态。  
2. 跑本地服务与 `dev_self_check.sh`，先拿到干净基线。  
3. 精准修改目标文件，避免跨模块“顺手重构”。  
4. 运行后端测试：

```bash
cd backend
pytest -q
```

5. 回到项目根目录跑脚本回归：

```bash
bash scripts/dev_self_check.sh
BASE_URL=http://localhost:3000 bash scripts/online_regression.sh
```

6. 记录结果：命令、时间、失败项、修复结论。  
7. 提交前同步更新 `docs/` 相关章节。  

## 5. 数据库迁移开发规范

- 新增/修改模型后，必须补 Alembic migration。
- 本地执行：

```bash
cd backend
alembic upgrade head
```

- 禁止只依赖 `create_all` 作为生产迁移手段。
- 提交时附上 migration 影响范围（表、列、索引、默认值）。

## 6. Dev Mode 与常见坑

### 代理变量误导

本地 shell 代理会导致 `curl localhost` 误报 502，命令统一带：

```bash
curl --noproxy '*' -sS http://localhost:3000/api/health
```

### Nuxt 生产入口误用

生产只允许 `npm run start`（即 `.output/server/index.mjs`）。  
不要跑 `.nuxt/dist/*` 或 `nuxt preview` 作为常驻进程。

### 脏工作区处理

仓库经常是脏工作区。原则：
- 不回退你没改的文件
- 提交只 stage 你负责的改动
- 改动涉及流程脚本时同步更新 docs

## 7. 交付与日志模板（开发侧）

建议在交付说明中固定包含：

```md
### 开发交付记录
- 时间：
- 代码版本：
- 目标问题：
- 修改文件：
- 验证命令：
- 结果摘要：
- 风险与后续：
```

## 8. 文档入口

- 根目录 `AGENTS.md` 是 Agent 的文档路由入口。
- 根目录 `README.md` 是人类读者的文档导航入口。
- 本文档是当前默认开发手册，后续上手流程以本文为准。
