# Trade Arena 运维自动化手册

最后更新：2026-03-31（Asia/Shanghai）

## 1. 目标

统一运维入口，减少人为差异操作。  
人类、Agent、Webhook 都尽量走同一套脚本与协议。  
Agent 的阅读路由以仓库根目录 `AGENTS.md` 为准。

## 2. 统一入口

### 2.1 CLI 入口

```bash
bash scripts/opsctl.sh <command>
```

常用命令：

```bash
bash scripts/opsctl.sh deploy --branch main
bash scripts/opsctl.sh migrate
bash scripts/opsctl.sh restart --target all
bash scripts/opsctl.sh status
bash scripts/opsctl.sh logs --scope deploy --tail 200
bash scripts/opsctl.sh smoke --profile local
bash scripts/opsctl.sh doctor
bash scripts/opsctl.sh init-secrets --output .env.ops.local
```

### 2.2 服务启停入口

日常本地开发启停仍使用：

```bash
bash scripts/service_ctl.sh <start|stop|restart|status>
```

### 2.3 远程 HTTP 脚本入口

用于值班同学或外部自动化系统直接调用网关：

```bash
export OPS_API_BASE=http://127.0.0.1:9000
export OPS_API_KEY=<your_ops_api_key>
bash scripts/ops_http.sh deploy --branch main --wait
bash scripts/ops_http.sh restart --target all --wait
bash scripts/ops_http.sh smoke --profile prod --base-url https://stock.cocoloop.cn --wait
bash scripts/ops_http.sh status
```

## 3. Webhook 与 HTTP 入口

- GitHub push：`POST /hooks/github/push`（旧地址 `POST /webhook` 仅临时兼容，需尽快切换）
- 健康检查：`GET /health`
- 日志读取：`GET /ops/logs`（需要 `Authorization: Bearer <OPS_API_KEY>`）

Ops API（同样需要 `Authorization: Bearer <OPS_API_KEY>`）：

- `POST /ops/jobs/deploy`
- `POST /ops/jobs/service`
- `POST /ops/jobs/migrate`
- `POST /ops/jobs/smoke`
- `POST /ops/jobs/doctor`
- `GET /ops/jobs/{job_id}`
- `GET /ops/status`
- `GET /ops/logs`

其中 `/ops/jobs/service` 支持 `target=all|backend|frontend`。

说明：

- GitHub push 事件会经过签名校验（`WEBHOOK_SECRET`）
- 分支会经过 allowlist 校验（`OPS_ALLOWED_BRANCHES`，默认 `main`）
- CI/CD 执行开始与结束会同步写入 `webhook/DEPLOY_LOG.md`

## 4. 必要环境变量

- `WEBHOOK_SECRET`：GitHub Webhook 签名密钥（生产必填）
- `OPS_API_KEY`：运维接口访问密钥（生产与 staging 必填）
- `OPS_ALLOWED_BRANCHES`：允许部署的分支列表，例如 `main` 或 `main release`
- `OPS_ENV`：`local|staging|prod`
- `OPS_PROJECT_ROOT`：项目根目录（默认当前仓库）
- `OPS_HTTP_CHECK_RETRIES`：部署后路由检查重试次数（默认 10）
- `OPS_HTTP_CHECK_INTERVAL`：部署后路由检查重试间隔秒数（默认 2）

建议先生成密钥文件：

```bash
bash scripts/opsctl.sh init-secrets --output .env.ops.local
```

也可以从 `.env.ops.example` 复制并手工配置。

## 5. 当前实现边界（阶段 2）

- 已启用：统一入口 `opsctl`、分支白名单、日志接口鉴权、HTTP job 队列
- 已启用：runner 锁、队列消费、job 状态追踪（`queued/running/succeeded/failed/cancelled`）
- 未启用：远程 rollback、gateway 自重启
- 生产恢复默认策略仍是“提交回滚 + 再部署”

## 6. 风险控制

- 不要把任意 shell 命令直接暴露为 HTTP 接口
- 不要在生产使用默认密钥或空密钥
- 不要绕过 `opsctl` 直接改部署脚本流程
- 改动运维脚本后，必须同步更新 `AGENTS.md`、`README.md` 与 `docs/ops-reference-manual.md`

## 7. CI 护栏

仓库已增加 `/.github/workflows/ci.yml`，包含：

- 后端 `pytest -q`
- 前端 `npm run build`
- shell 脚本 `shellcheck`
- webhook Python 语法检查
