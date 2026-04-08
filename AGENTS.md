不要把功能说明写到 UI 文案里！我求你了！

## Agent 文档路由（强制）

`AGENTS.md` 只给 Agent 看，只负责说明当前任务应该去读哪份 `docs/`。  
仓库根目录 `README.md` 给人类看，不作为 Agent 的上手入口。

执行任何改动、测试、部署前，按任务读取：

1. 任何代码改动前先读 `docs/developer-handbook.md`
2. 本地启动、联调、服务启停、Nuxt 本地排障时读 `docs/junior-dev-ops-handbook.md`
3. 部署、Webhook、迁移、回归、运行状态、日志读取时读 `docs/ops-reference-manual.md`
4. 执行测试前先读 `docs/testing-process-manual.md`
5. 落测试项时结合 `docs/testing-checklist.md`
6. 首次建机、systemd、Nginx、云服务器部署细节看 `docs/cloud-deployment-guide.md`
7. 参赛 Agent 进程部署与更新看 `docs/agent-server-deployment-runbook.md`
8. 操作本项目线上服务器时，优先看 `docs/ssh-skill-ops-handbook.md`，并优先使用 `ssh-skill`

若代码改动导致流程变化，提交中同步更新对应 `docs/`，并在需要时更新本文件的路由说明。

## 交接索引

- 开发入口：`docs/developer-handbook.md`
- 本地启动与联调：`docs/junior-dev-ops-handbook.md`
- 部署、迁移、日志与回归：`docs/ops-reference-manual.md`
- 生产数据逻辑删除留档：`docs/ops-logical-delete-log.md`
- 测试流程：`docs/testing-process-manual.md`
- 测试检查项：`docs/testing-checklist.md`
- 线上回归交接：`docs/ops-runbook-online-regression-and-handoff.md`
- 线上服务器 SSH 运维：`docs/ssh-skill-ops-handbook.md`
- 历史规划与阶段方案：`docs/plans/`

## 执行约束（强制）

- 本地长期启停统一走 `scripts/service_ctl.sh`，具体命令和排查顺序看 `docs/junior-dev-ops-handbook.md`
- 运维动作优先走 `scripts/opsctl.sh` 与 `scripts/ops_http.sh`，具体命令、边界和鉴权要求看 `docs/ops-reference-manual.md`
- 不要把 `uvicorn`、`npm run dev`、`npm run start` 当成长期开启或运维入口

## 生产数据删除约束（强制）

- 对任何生产环境数据，禁止执行硬删除（包括 SQL `DELETE`、`TRUNCATE`、直接物理清理）。
- 生产数据删除只允许逻辑删除（如 `is_deleted`、`deleted_at`、`deleted_by`、`delete_reason`）。
- 每次执行逻辑删除前后，都必须在 `docs/ops-logical-delete-log.md` 留档，记录操作者、审批人、影响范围、执行命令、回滚方案与结果。
- 未完成留档的删除动作视为违规操作，不允许执行。

## 当前仓库硬约束

- GitHub push webhook 入口统一为 `POST /hooks/github/push`
- 日志读取统一走 `/ops/logs`
- 远程运维动作统一走 `/ops/jobs/*` 与 `/ops/status`、`/ops/logs`
- `/ops/jobs/service` 的 `target` 允许 `all|backend|frontend`
- 不开放远程 rollback 与 gateway 自重启动作
- 生产和 staging 必须显式设置 `WEBHOOK_SECRET` 与 `OPS_API_KEY`
- 线上服务器仓库路径按当前项目约定使用 `/etc/nginx/website/trade-arena`
- 线上 SSH 运维统一按“密码引导一次，长期走密钥认证 + 连接复用”执行

## Nuxt 问题去哪里看

- 本地 `npm run dev`、`.nuxt`、`#app-manifest`、`#internal/nuxt/paths`：`docs/junior-dev-ops-handbook.md`
- 生产构建产物、`.output/server/index.mjs`、systemd 启动：`docs/cloud-deployment-guide.md` 与 `docs/ops-reference-manual.md`
