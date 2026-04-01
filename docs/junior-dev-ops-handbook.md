# Trade Arena 本地开发与联调手册

最后更新：2026-03-31（Asia/Shanghai）

这份手册用于本地启动、联调、重启、排查和最小验证。日常开发优先看这一份，不再分散查看多份本地运维说明。

## 1. 最常用的 6 条命令

启动开发环境：

```bash
MODE=dev START_DOCKER=1 BUILD_FRONTEND=0 bash scripts/service_ctl.sh start
```

查看状态：

```bash
bash scripts/service_ctl.sh status
```

重启开发环境：

```bash
MODE=dev START_DOCKER=1 BUILD_FRONTEND=0 bash scripts/service_ctl.sh restart
```

停止开发环境：

```bash
bash scripts/service_ctl.sh stop
```

停止并关闭 Docker 依赖：

```bash
STOP_DOCKER=1 bash scripts/service_ctl.sh stop
```

执行本地自检：

```bash
bash scripts/dev_self_check.sh
```

## 2. 本地启动标准顺序

推荐顺序：

```bash
MODE=dev START_DOCKER=1 BUILD_FRONTEND=0 bash scripts/service_ctl.sh start
bash scripts/dev_self_check.sh
```

默认端口：

- 前端：`http://localhost:3000`
- 后端：`http://localhost:8000`
- PostgreSQL：`localhost:5432`
- Redis：`localhost:6379`

如果当前机器已经有 PostgreSQL 和 Redis，可跳过 Docker：

```bash
MODE=dev START_DOCKER=0 BUILD_FRONTEND=0 bash scripts/service_ctl.sh start
```

如果本机或受限环境里 `uvicorn --reload` 的文件监听报错，可临时关闭后端热重载：

```bash
MODE=dev START_DOCKER=0 BUILD_FRONTEND=0 BACKEND_RELOAD=0 bash scripts/service_ctl.sh start
```

## 3. 日常开发后的最小验证

推荐顺序：

```bash
bash scripts/dev_self_check.sh
cd backend && pytest -q
cd ..
RUN_REGISTER=0 BASE_URL=http://127.0.0.1:3000 bash scripts/online_regression.sh
```

如果只想先做一轮轻量检查，用：

```bash
bash scripts/dev_self_check.sh
```

如果要看运维脚本和环境状态，再补：

```bash
bash scripts/opsctl.sh doctor
bash scripts/opsctl.sh status
bash scripts/opsctl.sh admin-login-guard list --active-only
```

## 4. 统一启停约束

平时不要手动常驻执行下面这些命令：

- `uvicorn app.main:app ...`
- `npm run dev`
- `npm run start`

统一使用：

- `bash scripts/service_ctl.sh start`
- `bash scripts/service_ctl.sh stop`
- `bash scripts/service_ctl.sh restart`
- `bash scripts/service_ctl.sh status`

如果只是查看日志、状态、部署记录，优先用：

- `bash scripts/opsctl.sh status`
- `bash scripts/opsctl.sh logs --scope deploy --tail 200`
- `bash scripts/opsctl.sh doctor`
- `bash scripts/opsctl.sh admin-login-guard list --active-only`

## 5. 代理环境的常见坑

如果 shell 里配置了 `http_proxy`、`https_proxy` 或 `all_proxy`，直接访问 `localhost` 可能会误报 `502`。

排查本地服务时，命令统一带上：

```bash
curl --noproxy '*' -sS http://localhost:8000/api/health
curl --noproxy '*' -I http://localhost:3000
curl --noproxy '*' -sS http://localhost:3000/api/health
curl --noproxy '*' -sS 'http://localhost:3000/api/leaderboard?market=overall'
```

浏览器能打开页面，但命令行返回 `502` 时，先怀疑代理，不要先判断服务挂了。

## 6. 本地健康检查与代理链路

后端健康检查：

```bash
curl --noproxy '*' -sS http://localhost:8000/api/health | python3 -m json.tool
```

期望结果：

```json
{
  "status": "ok",
  "db": true,
  "redis": true
}
```

前端 API 代理入口：

- `frontend/server/api/[...path].ts`

浏览器访问 `http://localhost:3000/api/*` 时，由 Nuxt 服务端转发到 `http://127.0.0.1:8000/*`。如果后端地址变化，优先检查这个文件。

## 7. 自检脚本常用模式

标准执行：

```bash
bash scripts/dev_self_check.sh
```

只验证脚本基础能力：

```bash
REQUIRE_PORTS=0 CHECK_DOCKER=0 RUN_HTTP_CHECKS=0 bash scripts/dev_self_check.sh
```

非默认端口：

```bash
FRONTEND_BASE=http://localhost:3001 BACKEND_BASE=http://localhost:8001 bash scripts/dev_self_check.sh
```

通过标准：

- 输出 `Summary: pass=... warn=... fail=0`
- 退出码为 `0`

## 8. 测试数据与开发接口

查看开发数据状态：

```bash
curl --noproxy '*' -sS http://localhost:8000/api/dev/status | python3 -m json.tool
```

生成测试数据：

```bash
curl --noproxy '*' -X POST http://localhost:8000/api/dev/mock
```

清空测试数据：

```bash
curl --noproxy '*' -X POST http://localhost:8000/api/dev/reset
```

这些接口只用于本地联调和回归，不要写进生产流程。

## 9. 构建与生产模式检查

如果只是确认“当前代码能不能正常构建”，优先用：

```bash
bash scripts/prod_build_check.sh
```

如果要本地以生产模式启动整套服务，用：

```bash
MODE=prod START_DOCKER=1 BUILD_FRONTEND=1 bash scripts/service_ctl.sh start
```

生产模式下前端正式入口应是 `.output/server/index.mjs`。不要把 `nuxt preview` 或 `.nuxt/dist/*` 当成常驻生产入口。

## 10. 页面打不开时的排查顺序

第一步看状态：

```bash
bash scripts/service_ctl.sh status
```

第二步做本地自检：

```bash
bash scripts/dev_self_check.sh
```

第三步看关键地址：

```bash
curl --noproxy '*' -sS http://localhost:8000/api/health
curl --noproxy '*' -I http://localhost:3000
```

第四步再看运维状态和日志：

```bash
bash scripts/opsctl.sh status
bash scripts/opsctl.sh logs --scope deploy --tail 200
```

如果是后台口令连续输错后被拦截，再补一条：

```bash
bash scripts/opsctl.sh admin-login-guard list --active-only
```

## 11. 本地敏感运维补充

本地机器需要单独记录服务器地址、账号、口令等敏感信息时，统一写到：

```bash
docs/junior-dev-ops-handbook.local.md
```

该文件已加入 `.gitignore`，不要把敏感信息写进受版本控制的文档。

## 12. 相关文档

需要更完整的开发流程时继续看：

- `docs/developer-handbook.md`
- `docs/testing-process-manual.md`
- `docs/testing-checklist.md`

涉及部署、Webhook、迁移、日志和线上排障时继续看：

- `docs/ops-reference-manual.md`
- `docs/ops-runbook-online-regression-and-handoff.md`
- `docs/ops-automation-manual.md`
