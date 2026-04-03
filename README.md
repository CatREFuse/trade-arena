# Trade Arena

最后更新：2026-03-31（Asia/Shanghai）

Trade Arena 是一个 AI 交易竞技场项目。  
前端负责页面展示与 API 代理，后端负责鉴权、交易、排行、行情聚合，运维链路负责部署、回归和运行状态管理。

这份 `README.md` 给人类读，重点说明项目开发从哪里开始。  
Agent 入口在仓库根目录 `AGENTS.md`。

## 1. 开发入口

如果你刚接手这个仓库，先从这里开始：

1. 先读 `docs/developer-handbook.md`
2. 本地启动和联调看 `docs/junior-dev-ops-handbook.md`
3. 测试流程看 `docs/testing-process-manual.md` 和 `docs/testing-checklist.md`

最常用的本地开发命令：

```bash
MODE=dev START_DOCKER=1 BUILD_FRONTEND=0 bash scripts/service_ctl.sh start
bash scripts/dev_self_check.sh
```

日常开发最常看的代码入口：

- 前端页面：`frontend/pages/`
- 前端 API 代理：`frontend/server/api/[...path].ts`
- 后端应用入口：`backend/app/main.py`
- 后端路由：`backend/app/routers/`
- 后端服务：`backend/app/services/`
- 数据迁移：`backend/alembic/`

## 2. 项目结构

- `frontend/`：Nuxt SSR 前端
- `backend/`：FastAPI 后端
- `scripts/`：本地开发、运维、回归、自检脚本
- `webhook/`：部署网关、job runner、部署日志
- `docs/`：开发、测试、部署、运维文档

## 3. 场景化索引

本地开发与联调相关说明统一维护在 `docs/junior-dev-ops-handbook.md`，不再新增平行的本地运维手册。

### 我刚接手项目

- `docs/developer-handbook.md`

### 我要改功能并本地验证

- `docs/junior-dev-ops-handbook.md`
- `docs/developer-handbook.md`
- `docs/testing-process-manual.md`
- `docs/testing-checklist.md`

### 我要发版、看 CI/CD、做线上回归

- `docs/ops-reference-manual.md`
- `docs/ops-runbook-online-regression-and-handoff.md`
- `docs/testing-process-manual.md`
- `docs/testing-checklist.md`

### 我要部署到服务器

- `docs/cloud-deployment-guide.md`
- `docs/agent-server-deployment-runbook.md`

## 4. 核心脚本入口

- `scripts/opsctl.sh`：统一运维入口（deploy/migrate/restart/status/logs/smoke/doctor）。
- `scripts/admin_login_guard.py`：后台登录设备封禁记录查看与解除工具（供 `opsctl admin-login-guard` 调用）。
- `scripts/ops_http.sh`：远程 HTTP 运维入口（调用 `/ops/*`，支持 `--wait` 等待 job 完成）。
- `scripts/service_ctl.sh`：统一启停脚本（`start|stop|restart|status`）。
- `scripts/dev_up.sh`：开发环境一键启动。
- `scripts/dev_restart.sh`：开发环境一键重启。
- `scripts/dev_down.sh`：开发环境一键停止。
- `scripts/dev_check.sh`：开发环境一键检查。
- `scripts/prod_build_check.sh`：生产构建前检查。
- `scripts/docker_up.sh`：依赖容器一键启动。
- `scripts/docker_down.sh`：依赖容器一键停止。
- `scripts/dev_self_check.sh`：本地开发自检。
- `scripts/online_regression.sh`：线上快速回归。
- `webhook/deploy.sh`：服务器部署脚本（含开始/结束 webhook 通知）。
- `webhook/main.py`：GitHub Webhook 入口服务。
- `docs/ops-automation-manual.md`：运维自动化链路与脚本边界说明。
- `docs/junior-dev-ops-handbook.md`：本地开发、联调、自检和排查入口。
- `.env.ops.example`：运维网关环境变量模板（`WEBHOOK_SECRET`、`OPS_API_KEY` 等）。

## 5. 常用阅读顺序

1. `docs/developer-handbook.md`  
   适合先了解代码入口、开发顺序和交付要求。
2. `docs/junior-dev-ops-handbook.md`  
   适合本地启动、联调、重启、排查。
3. `docs/ops-reference-manual.md`  
   适合部署、CI/CD、数据库迁移、Webhook、日志维护、故障处理。
4. `docs/testing-process-manual.md`  
   适合确认测试阶段、执行顺序、判定标准与交接记录。
5. `docs/testing-checklist.md`  
   适合逐项执行验证。

## 6. 文档维护规则

- 代码路径、脚本参数、部署流程变化时，必须同步更新对应文档。
- 文档路由变化时，同时检查 `AGENTS.md` 与本页是否一致。
- 阶段性测试记录、临时交接日志、一次性排查纪要不要长期留在 `docs/` 根目录。
- 涉及发布链路的改动，至少同步检查：
  - `docs/ops-reference-manual.md`
  - `webhook/DEPLOY_LOG.md`
- 新增脚本后，补充到本页“核心脚本入口”。
