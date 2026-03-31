# Trade Arena 文档导航（Agent 入口）

最后更新：2026-03-31（Asia/Shanghai）

本目录是项目文档唯一入口。所有 Agent 在改代码、跑测试、执行部署前，先按下列顺序阅读。

## 1. 强制阅读顺序

1. `docs/developer-handbook.md`  
   目标：快速定位改动点、明确开发与验证顺序。
2. `docs/ops-reference-manual.md`  
   目标：部署、CI/CD、数据库迁移、Webhook、日志维护、故障处理。
3. `docs/testing-process-manual.md`  
   目标：统一测试阶段、执行顺序、判定标准与交接记录。
4. `docs/testing-checklist.md`  
   目标：按条目执行具体验证项。

## 2. 场景化索引

### 我刚接手项目

- `docs/developer-handbook.md`
- `交接文档.md`（兼容入口）

### 我要改功能并本地验证

- `docs/developer-handbook.md`
- `docs/ops-runbook-local-development-and-test-server.md`
- `docs/testing-process-manual.md`
- `docs/testing-checklist.md`
- `docs/testing-dev-server-squad-report-2026-03-31.md`（本期 dev 小队测试记录）

### 我要发版、看 CI/CD、做线上回归

- `docs/ops-reference-manual.md`
- `docs/ops-runbook-online-regression-and-handoff.md`
- `docs/testing-process-manual.md`
- `docs/testing-checklist.md`

### 我要部署到服务器

- `docs/cloud-deployment-guide.md`
- `docs/agent-server-deployment-runbook.md`

## 3. 核心脚本入口

- `scripts/opsctl.sh`：统一运维入口（deploy/migrate/restart/status/logs/smoke/doctor）。
- `scripts/ops_http.sh`：远程 HTTP 运维入口（调用 `/ops/*`，支持 `--wait` 等待 job 完成）。
- `scripts/service_ctl.sh`：统一启停脚本（`start|stop|restart|status`）。
- `scripts/dev_self_check.sh`：本地开发自检。
- `scripts/online_regression.sh`：线上快速回归。
- `webhook/deploy.sh`：服务器部署脚本（含开始/结束 webhook 通知）。
- `webhook/main.py`：GitHub Webhook 入口服务。
- `docs/ops-automation-manual.md`：人类与 Agent 共读的运维自动化手册。
- `.env.ops.example`：运维网关环境变量模板（`WEBHOOK_SECRET`、`OPS_API_KEY` 等）。

## 4. 文档维护规则

- 代码路径、脚本参数、部署流程变化时，必须同步更新对应文档。
- 涉及发布链路的改动，至少同步检查：
  - `docs/ops-reference-manual.md`
  - `webhook/DEPLOY_LOG.md`
- 新增脚本后，补充到本页“核心脚本入口”。
