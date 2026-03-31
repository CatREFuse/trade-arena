# Trade Arena 运维参考手册

最后更新：2026-03-31（Asia/Shanghai）

本文档面向接手部署与集成构建工作的 Agent，目标是让你在首次接手时就能稳定完成：
- 触发并观察 CI/CD
- 执行数据库迁移
- 维护 webhook 与部署日志
- 故障时快速止损并恢复服务

## 1. 运行拓扑与关键路径

- Nginx：对外入口
- Frontend（Nuxt SSR）：`127.0.0.1:3000`
- Backend（FastAPI）：`127.0.0.1:8000`
- PostgreSQL + Redis：容器/本机服务
- Webhook 服务：接收 GitHub `push`，调用部署脚本

关键文件：
- `webhook/main.py`：Webhook 接收、签名校验、排队逻辑、触发部署
- `webhook/deploy.sh`：实际部署执行器
- `webhook/config.py`：Webhook/日志/锁文件配置
- `webhook/DEPLOY_LOG.md`：Markdown 格式部署事件记录
- `/var/log/trade-arena-deploy.log`：部署运行日志（服务器）

## 2. CI/CD 流程（当前实现）

### 2.1 触发链路

1. GitHub `push` 请求到 `/webhook`
2. `webhook/main.py` 使用 `X-Hub-Signature-256` + `WEBHOOK_SECRET` 验签
3. 若存在 `/tmp/trade-arena-deploy.lock`：写入待处理分支 `/tmp/trade-arena-pending-deploy` 并记入 `webhook/DEPLOY_LOG.md`
4. 否则直接后台执行 `webhook/deploy.sh <branch>`

### 2.2 部署脚本执行序列

`webhook/deploy.sh` 当前顺序：

1. 上锁：`/tmp/trade-arena-deploy.lock`
2. 记录开始信息并触发 webhook（阶段=开始）
3. `git fetch origin && git checkout <branch>`
4. 强制对齐远端：`git reset --hard origin/<branch> && git clean -fd`
5. 安装后端依赖并执行 `alembic upgrade head`
6. 前端 `npm ci && npm run build`（重建 `.output`）
7. 重启后端与前端进程
8. 健康检查与关键路由检查
9. 退出时统一触发 webhook（阶段=结束，成功/失败）

### 2.3 开始/结束通知规则

脚本会向以下地址发通知：

- `https://api.day.app/kGX9fqRpLM9SjjVvNtHcJc/Stock运维/<encoded_info>`

通知内容包含：
- 分支信息（目标分支、当前分支）
- 提交信息（部署前后 commit）
- 开始/结束时间（UTC）
- 退出码与结果（成功/失败）

实现细节：
- 使用 `urlencode()` 对整个信息文本做 URL 编码，确保特殊字符可安全传输。

## 3. 部署前后操作清单

### 3.1 部署前

- 确认目标分支可用，避免将未审核提交直接部署。
- 确认数据库迁移脚本已随代码入库。
- 确认 `WEBHOOK_SECRET` 已在服务器环境变量中设置（不要使用默认值）。

### 3.2 部署后

按顺序检查：

1. 运行日志：`tail -n 200 /var/log/trade-arena-deploy.log`
2. Webhook 记录：检查 `webhook/DEPLOY_LOG.md` 最新条目状态
3. 线上回归：

```bash
bash scripts/online_regression.sh
```

4. 若失败，先看日志再决定回滚或热修复

## 4. 数据库迁移 SOP（强制）

### 4.1 开发阶段

在 `backend/`：

```bash
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

要求：
- 每次模型变更必须有 migration
- 不允许仅依赖 `create_all`
- 提交前确认 migration 可重复执行（空变更不应报错）

### 4.2 部署阶段

- 统一由 `webhook/deploy.sh` 执行 `alembic upgrade head`
- 若迁移失败，部署视为失败，必须先修复迁移再重试

### 4.3 回滚建议

- 优先使用“提交回滚 + 再部署”
- 对数据库结构回滚要有明确 downgrade 脚本与数据影响评估
- 在无充分验证前，不要直接在线上执行高风险 downgrade

## 5. 日志维护规范

### 5.1 两类日志的职责

- `webhook/DEPLOY_LOG.md`：事件级日志（谁推了什么、是否触发/排队）
- `/var/log/trade-arena-deploy.log`：执行级日志（构建、迁移、重启、健康检查细节）

### 5.2 维护原则

- 问题定位优先看执行级日志，再结合事件级日志补上下文
- 交接记录需要包含：时间、分支、commit、失败步骤、修复动作
- 对外沟通时隐藏敏感信息（token、secret、完整邮箱等）

## 6. 故障处理与恢复

### 6.1 常见故障入口

- Webhook 401：签名错误或 `WEBHOOK_SECRET` 不一致
- 部署一直排队：锁文件未清理
- 前端启动异常：误用 `.nuxt` 产物，或构建产物损坏
- API 500：迁移未完成或依赖安装失败

### 6.2 快速处理顺序

1. 看 `/var/log/trade-arena-deploy.log`
2. 看 `webhook/DEPLOY_LOG.md`
3. 验证进程与端口
4. 执行快速回归脚本
5. 必要时回滚提交并重新部署

## 7. 值班交接模板（建议）

```md
### 运维交接记录
- 时间（Asia/Shanghai）：
- 分支与提交：
- CI/CD 结果：
- 迁移结果：
- 回归结果：
- 异常与处理：
- 待办与风险：
```

## 8. 关联文档

- `docs/developer-handbook.md`
- `docs/testing-checklist.md`
- `docs/cloud-deployment-guide.md`
- `docs/ops-runbook-online-regression-and-handoff.md`
