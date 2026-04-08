# Trade Arena 运维参考手册

最后更新：2026-04-07（Asia/Shanghai）

本文档面向接手部署与集成构建工作的 Agent，目标是让你在首次接手时就能稳定完成：
- 触发并观察 CI/CD
- 执行数据库迁移
- 维护 webhook 与部署日志
- 故障时快速止损并恢复服务
- 严格按逻辑删除流程处理生产数据删除

操作本项目线上服务器时，优先结合 `docs/ssh-skill-ops-handbook.md` 使用 `ssh-skill`。

## 1. 运行拓扑与关键路径

- Nginx：对外入口
- Frontend（Nuxt SSR）：`127.0.0.1:3000`
- Backend（FastAPI）：`127.0.0.1:8000`
- PostgreSQL + Redis：容器/本机服务
- Webhook 服务：接收 GitHub `push`，调用部署脚本

关键文件：
- `scripts/opsctl.sh`：统一运维入口（deploy/migrate/restart/status/logs/smoke/doctor）
- `scripts/ops_http.sh`：远程 HTTP 运维入口（调用 `/ops/*`，支持等待 job）
- `webhook/main.py`：Webhook 接收、签名校验、排队逻辑、触发部署
- `webhook/deploy.sh`：实际部署执行器
- `webhook/config.py`：Webhook/日志/锁文件配置
- `scripts/service_ctl.sh`：服务启停统一脚本（start/stop/restart/status）
- `webhook/DEPLOY_LOG.md`：Markdown 格式部署事件记录
- `/var/log/trade-arena-deploy.log`：部署运行日志（服务器）
- `docs/ops-logical-delete-log.md`：生产环境逻辑删除留档

线上服务器 SSH 配置入口：

- 本地凭据模板：`.env.ssh.trade-arena.example`
- 本地实际凭据：`.env.ssh.trade-arena.local`（已加入 `.gitignore`）
- 一键生成 ssh-skill 配置：`bash scripts/setup_trade_arena_ssh_skill.sh`
- 一键切换为高性能密钥认证：`bash scripts/bootstrap_trade_arena_ssh_key_auth.sh`
- 原生 SSH 快速执行：`bash scripts/trade_arena_ssh.sh "<command>"`
- 复用连接预热：`bash scripts/trade_arena_ssh_master.sh start`
- 详细说明：`docs/ssh-skill-ops-handbook.md`
- 当前线上仓库路径：`/etc/nginx/website/trade-arena`

## 2. CI/CD 流程（当前实现）

### 2.1 触发链路

1. GitHub `push` 请求到 `/hooks/github/push`（旧地址 `/webhook` 仅保留迁移兼容）
2. `webhook/main.py` 使用 `X-Hub-Signature-256` + `WEBHOOK_SECRET` 验签
   若分支不在 `OPS_ALLOWED_BRANCHES`（默认 `main`），请求会被忽略
   Webhook 请求体兼容 `application/json` 与 `application/x-www-form-urlencoded`（`payload=<json>`）
3. 网关创建 deploy job 并写入 `.runtime/ops/jobs/*.json` 与 `.runtime/ops/queue/*.queue`
4. `scripts/opsctl.sh run-next-job` 消费队列并执行实际部署动作

### 2.1.1 Ops API（白名单动作）

- `POST /ops/jobs/deploy`
- `POST /ops/jobs/service`
- `POST /ops/jobs/migrate`
- `POST /ops/jobs/smoke`
- `POST /ops/jobs/doctor`
- `GET /ops/jobs/{job_id}`
- `GET /ops/status`
- `GET /ops/logs`

`/ops/jobs/service` 的 `target` 允许 `all|backend|frontend`。

鉴权规则：

- 使用 `Authorization: Bearer <OPS_API_KEY>`
- 生产和 staging 必须设置 `OPS_API_KEY`
- 本地 `OPS_ENV=local` 仅允许 `127.0.0.1` 免密联调

密钥生成可使用：

```bash
bash scripts/opsctl.sh init-secrets --output .env.ops.local
```

`webhook/config.py` 启动时会自动读取项目根目录的 `.env.ops.local`（以及可选 `.env.ops`）并注入 `WEBHOOK_SECRET`、`OPS_API_KEY` 等变量。

### 2.2 部署脚本执行序列

`webhook/deploy.sh` 当前顺序：

1. 作为薄入口只负责转发到 `scripts/opsctl.sh deploy --branch <branch>`
2. 具体部署编排由 `scripts/ops/deploy.sh` 执行
3. 服务重启统一调用 `scripts/opsctl.sh restart --target all`（内部再转发到 `scripts/service_ctl.sh`，默认会拉起 webhook）
4. 实际部署脚本仍使用锁文件与 pending 机制，避免同机并发部署
5. 部署执行开始/结束会同步写入 `webhook/DEPLOY_LOG.md`

补充（2026-04）：
- `scripts/ops/deploy.sh` 对 `git fetch` 增加了超时与重试（默认 45 秒、3 次）
- 若发现锁文件存在但没有活跃 deploy 进程，会自动判定为僵尸锁并清理
- 可通过环境变量调优：`OPS_GIT_FETCH_TIMEOUT`、`OPS_GIT_FETCH_RETRIES`、`OPS_GIT_FETCH_RETRY_INTERVAL`

### 2.3 开始/结束通知规则

脚本会向以下地址发通知：

- `https://api.day.app/kGX9fqRpLM9SjjVvNtHcJc/Stock运维/<encoded_info>`

通知内容包含：
- 分支信息（目标分支、当前分支）
- 提交信息（部署前后 commit）
- 开始/结束时间（UTC）
- 退出码与结果（成功/失败）
- 失败上下文（`fail_context`，包含失败行号与失败命令）

实现细节：
- 使用 `urlencode()` 对整个信息文本做 URL 编码，确保特殊字符可安全传输。
- 控制台路由检查支持重试，降低启动瞬态导致的误报失败。

## 3. 部署前后操作清单

### 3.1 部署前

- 确认目标分支可用，避免将未审核提交直接部署。
- 确认数据库迁移脚本已随代码入库。
- 确认 `WEBHOOK_SECRET` 已在服务器环境变量中设置（不要使用默认值）。
- 【强制】先执行 `timeout 20 git ls-remote origin HEAD` 预检 Git 连通性；若超时，先走“3.4 Git host 重配 SOP”，再部署。
- 禁止直接修改线上服务器仓库工作树中的业务代码后再手动重启服务。
- 代码上线统一流程是：本地改动 -> 本地验证 -> `git commit` -> `git push` -> 等 webhook 自动 CI/CD 部署。
- 如果出现线上热修，必须立刻把同一改动补回本地仓库并重新 `git push`，让线上重新回到可追踪的 Git 状态。

### 3.2 部署后

按顺序检查：

1. 运行日志：`tail -n 200 /var/log/trade-arena-deploy.log`
2. Webhook 记录：检查 `webhook/DEPLOY_LOG.md` 最新条目状态
3. 线上回归：

```bash
bash scripts/online_regression.sh
```

4. 若失败，先看日志再决定回滚或热修复

服务状态可统一用脚本检查：

```bash
bash scripts/opsctl.sh status
bash scripts/service_ctl.sh status
```

运维日志读取需要鉴权：

```bash
curl --noproxy '*' -H "Authorization: Bearer <OPS_API_KEY>" "http://127.0.0.1:9000/ops/logs?scope=webhook&tail=200"
```

### 3.3 后台口令登录防护与 CLI 解封

`/console` 的口令登录启用了设备级请求防护：

- 服务端会为设备下发 `ta_console_device` 指纹 cookie。
- 同一设备连续输错 3 次口令后，登录请求会被暂停。
- 暂停时长按指数退避递增：首次 6 小时，之后 12 小时、24 小时、48 小时递增。
- 设备一旦成功登录，会清空该设备的连续失败次数和退避等级。

登录防护状态文件默认写入：

```bash
.runtime/admin-login-guard/state.json
```

公网入口要求：

- Nginx 必须将 `/api/admin/auth/` 代理到 `127.0.0.1:3000`
- 其余 `/api/` 仍可按现有规则代理到 `127.0.0.1:8000`
- 若漏掉这条例外，`/console/login` 页面对外会返回 `404`

运维排查与解除统一走 SSH CLI：

```bash
bash scripts/opsctl.sh admin-login-guard list --active-only
bash scripts/opsctl.sh admin-login-guard unblock --device-key <device_key>
```

如需按完整设备指纹解除，也可执行：

```bash
bash scripts/opsctl.sh admin-login-guard unblock --fingerprint <fingerprint>
```

处理顺序建议：

1. 先执行 `list --active-only` 找到仍在封禁中的 `device_key`
2. 与用户核对设备和时间窗口，避免误解封
3. 再执行 `unblock`
4. 如为重复触发，继续检查是否存在暴力尝试来源

### 3.4 Git host 重配 SOP（重点）

适用场景（任一满足就执行）：

- 部署日志持续停在 `git fetch attempt x/3`
- `timeout 20 git ls-remote origin HEAD` 超时
- webhook 已命中（200）但代码始终未拉到最新 commit

先进入线上仓库目录：

```bash
cd /etc/nginx/website/trade-arena
```

1) 先做连通性确认：

```bash
timeout 20 git ls-remote origin HEAD
```

2) 如果超时，探测可用 GitHub IP（返回 `200` 视为可用）：

```bash
for ip in 140.82.112.4 140.82.114.3 20.205.243.166; do
  curl --connect-timeout 5 --max-time 8 --resolve github.com:443:$ip -o /dev/null -s -w "$ip %{http_code}\n" https://github.com
done
```

3) 将可用 IP 写入 `/etc/hosts`（示例使用 `140.82.112.4`）：

```bash
if grep -qE '[[:space:]]github\.com(\s|$)' /etc/hosts; then
  sudo sed -i -E 's/^.*[[:space:]]github\.com(\s.*)?$/140.82.112.4 github.com/' /etc/hosts
else
  echo '140.82.112.4 github.com' | sudo tee -a /etc/hosts >/dev/null
fi
grep -n 'github.com' /etc/hosts
```

4) 复检 Git 连通性并重新部署：

```bash
timeout 60 git ls-remote origin HEAD
bash scripts/opsctl.sh deploy --branch main
```

强调：

- 这是生产故障恢复优先级最高的排障项之一，`git fetch` 卡住时不要反复盲目重试部署。
- 仅修改 `github.com` 映射，不要批量改写其它 host。
- 网络恢复后可评估是否恢复默认 DNS，避免长期依赖静态 IP。

### 3.5 生产数据删除 SOP（强制逻辑删除）

生产环境禁止硬删除。任何删除动作都必须满足下面流程：

1. 先在 `docs/ops-logical-delete-log.md` 新增“待执行”记录，补齐申请人、审批人、影响范围、回滚方案。
2. 仅执行逻辑删除语句（例如更新 `is_deleted/deleted_at/deleted_by/delete_reason`）。
3. 执行后补充同一条记录的执行结果和校验结果。
4. 未留档或留档字段不完整时，不允许执行删除动作。

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

- `webhook/DEPLOY_LOG.md`：事件级 + 执行级摘要日志（触发/排队、执行开始/结束、成功/失败、失败上下文）
- `/var/log/trade-arena-deploy.log`：执行级详细日志（构建、迁移、重启、健康检查细节）

### 5.2 维护原则

- 问题定位优先看执行级日志，再结合事件级日志补上下文
- 交接记录需要包含：时间、分支、commit、失败步骤、修复动作
- 对外沟通时隐藏敏感信息（token、secret、完整邮箱等）

## 6. 故障处理与恢复

### 6.1 常见故障入口

- Webhook 401：签名错误或 `WEBHOOK_SECRET` 不一致
- Webhook 503：`WEBHOOK_SECRET` 或 `OPS_API_KEY` 未正确配置
- 部署一直排队：锁文件未清理
- `git fetch` 卡住：默认会自动超时重试，超过重试上限后失败退出并记录失败上下文
- `git fetch` 连续超时：优先执行“3.4 Git host 重配 SOP（重点）”，不要只做重复 deploy
- `git` 同步报 `webhook/DEPLOY_LOG.md not uptodate`：旧部署遗留索引标记或本地日志改动
- 前端启动异常：误用 `.nuxt` 产物，或构建产物损坏
- API 500：迁移未完成或依赖安装失败
- `/console/login` 返回 429：设备指纹已进入登录冷却期，可用 `opsctl admin-login-guard` 排查与解除

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
- `docs/ssh-skill-ops-handbook.md`
