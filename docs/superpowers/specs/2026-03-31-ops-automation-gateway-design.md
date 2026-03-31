# 运维自动化与受控 HTTP 网关设计

最后更新：2026-03-31（Asia/Shanghai）
状态：已确认方案，待实现
适用范围：Trade Arena 仓库、部署服务器、Webhook 服务、Agent 协作规则

## 1. 目标

本设计要解决三件事：

1. 把当前分散的运维动作收口成一套统一脚本入口，避免“本地一套、线上一套、Webhook 一套”。
2. 把关键运维动作包装成受控 HTTP 协议，供人类、Agent、GitHub Webhook 使用，但不暴露任意 Shell 执行能力。
3. 把流程、入口、密钥和禁令写进文档与 `AGENTS.md`，降低运维工作对特定 Agent 的依赖。

最终结果应满足：

- 人类和 Agent 只记一个 CLI 入口：`scripts/opsctl.sh`
- 所有远程触发都只打一个 HTTP 网关
- 生产部署只允许白名单动作，不允许任意命令执行
- 生产服务控制统一走 `systemd`
- 本地开发与测试机保留 `scripts/service_ctl.sh`
- 仓库内补最小 CI，至少能在合并前发现 build 和测试问题
- 新方案必须给出明确的权限边界、队列恢复策略和迁移兼容策略

## 2. 非目标

本轮不做下面几项：

- 不做蓝绿部署、金丝雀发布、多环境矩阵
- 不引入复杂的消息队列、中控平台或外部运维 SaaS
- 不对公网暴露任意脚本、任意参数、任意文件读取能力
- 不要求把所有运维都并入业务后端 `backend/`

## 3. 现状问题

### 3.1 现有控制面分裂

当前至少有两套控制面：

- 本地控制面：`scripts/service_ctl.sh`、`scripts/dev_self_check.sh`、`scripts/online_regression.sh`
- 线上控制面：`webhook/main.py` + `webhook/deploy.sh`

结果是：

- 同一个“重启服务”在不同入口里有不同实现
- 线上部署没有复用本地已有的脚本能力
- 文档描述和线上实际行为已经漂移

### 3.2 现有部署链路风险偏高

当前 `webhook/deploy.sh` 存在以下问题：

- 服务器路径、通知地址、日志路径、锁文件路径都写死
- 使用 `git reset --hard` 与 `git clean -fd`
- 直接 `pkill` / `nohup`
- 生产后端仍带 `uvicorn --reload`
- 没有 branch allowlist
- 没有 job 状态管理，只靠单个 pending 文件

### 3.3 安全边界不够清楚

- `WEBHOOK_SECRET` 仍有默认值，容易带着默认配置上线
- `/webhook/logs` 目前无鉴权
- 日志内容可能包含推送邮箱、分支名、提交信息
- 当前接口边界更像“部署脚本裸调用”，不是“受控运维协议”

### 3.4 仓库内 CI 缺失

当前没有 `.github/workflows`。这意味着：

- 没有合并前测试护栏
- 没有前端 build 护栏
- 没有 shell 脚本静态检查
- CD 失败常常要到服务器上才暴露

## 4. 设计原则

1. 单一入口。所有运维动作都要能从 `scripts/opsctl.sh` 进入。
2. 单一真相。HTTP 网关不能写第二套业务逻辑，只能调统一脚本入口。
3. 白名单动作。开放的是“命名动作”，不是远程 shell。
4. 环境分层。生产走 `systemd`，本地走 `service_ctl.sh`。
5. 默认安全。密钥必须显式配置，日志默认脱敏，分支默认受限。
6. 可审计。每个远程动作必须有 `job_id`、触发来源、执行日志和最终状态。
7. 可降级。即使 HTTP 网关不可用，人类仍可以直接用 `scripts/opsctl.sh` 完成恢复。

## 5. 总体方案

整体收成三层：

### 5.1 脚本层

新增统一入口：

```bash
bash scripts/opsctl.sh <command> [args...]
```

`opsctl` 负责：

- 参数解析
- 环境装载
- 动作路由
- 统一日志格式
- 返回统一退出码

动作本体拆到 `scripts/ops/`：

- `scripts/ops/lib/env.sh`
- `scripts/ops/lib/log.sh`
- `scripts/ops/lib/lock.sh`
- `scripts/ops/lib/job.sh`
- `scripts/ops/git_sync.sh`
- `scripts/ops/backend_prepare.sh`
- `scripts/ops/frontend_prepare.sh`
- `scripts/ops/migrate.sh`
- `scripts/ops/service.sh`
- `scripts/ops/health.sh`
- `scripts/ops/regression.sh`
- `scripts/ops/notify.sh`
- `scripts/ops/deploy.sh`
- `scripts/ops/rollback.sh`
- `scripts/ops/logs.sh`
- `scripts/ops/status.sh`
- `scripts/ops/doctor.sh`

### 5.2 HTTP 网关层

保留 `webhook/` 目录，但把它从“GitHub Webhook 接收器”升级成“受控运维网关”。

职责：

- GitHub HMAC 验签
- Ops API Key 鉴权
- job 入队
- job 状态查询
- 日志访问控制
- 统一调用 `scripts/opsctl.sh`

非职责：

- 不直接拼接 shell 命令
- 不直接实现部署逻辑
- 不开放任意路径和任意文件读取
- 第一阶段不提供“远程重启自己”与“远程重启全部服务”

### 5.3 CI 层

新增最小 GitHub Actions：

- 后端测试
- 前端 build
- shellcheck
- 基础文档/脚本存在性检查

CI 只做“验证”，不负责部署。

## 6. 统一 CLI 设计

### 6.1 命令面

统一入口定义为：

```bash
bash scripts/opsctl.sh status
bash scripts/opsctl.sh logs --scope deploy --tail 200
bash scripts/opsctl.sh deploy --branch main
bash scripts/opsctl.sh migrate
bash scripts/opsctl.sh restart --target backend
bash scripts/opsctl.sh gateway-reload
bash scripts/opsctl.sh smoke --profile prod
bash scripts/opsctl.sh doctor
```

### 6.2 标准命令

- `deploy`
- `migrate`
- `build-frontend`
- `restart`
- `gateway-reload`
- `status`
- `logs`
- `smoke`
- `doctor`

### 6.3 命令职责

`deploy`

- 获取锁
- 校验分支与 ref
- 同步代码
- 安装依赖
- 运行迁移
- 构建前端
- 重启 backend/frontend
- 运行健康检查
- 记录结果与通知
- 如果本次变更包含 gateway 相关文件，则把 `gateway_reload_required=true` 写入 job 摘要

`restart`

- 生产环境只允许通过受限包装器控制 backend/frontend
- 本地和测试机可代理到 `scripts/service_ctl.sh`

`gateway-reload`

- 只允许本地 CLI 执行，不开放 HTTP
- 执行前必须确认队列为空且无 `running` job
- 使用延迟重启或单独 wrapper 完成 gateway 进程切换
- 用于让新的 `webhook/main.py` / `scripts/opsctl.sh` 生效

`smoke`

- 本地 profile 调 `scripts/dev_self_check.sh`
- 线上 profile 调 `scripts/online_regression.sh`

`doctor`

- 检查配置、端口、systemd 状态、锁文件、job 队列、关键目录

## 7. 统一 HTTP 协议设计

### 7.1 协议目标

HTTP 对外暴露的是“运维动作协议”，不是“脚本执行协议”。

### 7.2 鉴权模型

#### GitHub Webhook

- 接口：`POST /hooks/github/push`
- 鉴权：`X-Hub-Signature-256`
- 密钥：`WEBHOOK_SECRET`
- 约束：只允许白名单分支触发部署，默认仅 `main`

#### Ops 网关

- 鉴权头：`Authorization: Bearer <OPS_API_KEY>`
- 必填密钥：`OPS_API_KEY`
- 可选增强：
  - `OPS_ALLOWED_IPS`
  - `X-Ops-Timestamp`
  - `X-Ops-Signature`

第一阶段强制要求：

- `OPS_API_KEY` 无默认值
- 缺失则服务拒绝启动
- 仅 `OPS_ENV=local` 时允许缺失；此时非 GitHub 写接口只监听 `127.0.0.1`，且仅用于本地联调

### 7.3 API 列表

#### 写操作

`POST /ops/jobs/deploy`

请求体：

```json
{
  "branch": "main",
  "ref": "origin/main",
  "source": "human|agent|github",
  "reason": "manual deploy after fix"
}
```

`POST /ops/jobs/service`

```json
{
  "action": "restart",
  "target": "backend|frontend"
}
```

`POST /ops/jobs/migrate`

```json
{
  "revision": "head"
}
```

`POST /ops/jobs/smoke`

```json
{
  "profile": "prod",
  "base_url": "https://stock.cocoloop.cn"
}
```

#### 读操作

`GET /ops/jobs/{job_id}`

返回：

```json
{
  "job_id": "job_20260331_001",
  "type": "deploy",
  "status": "queued|running|succeeded|failed|cancelled",
  "result_reason": "orphaned|superseded|manual_cancelled|none",
  "created_at": "2026-03-31T12:00:00+08:00",
  "started_at": "2026-03-31T12:00:02+08:00",
  "finished_at": "2026-03-31T12:04:30+08:00",
  "summary": "frontend build ok, smoke ok"
}
```

`GET /ops/status`

返回系统状态、最近 job、锁状态、关键服务状态。

`GET /ops/logs`

查询参数：

- `scope=deploy|gateway|backend|frontend|job`
- `job_id=<id>`
- `tail=200`

说明：

- 只返回脱敏日志
- 不返回任意文件

### 7.4 job 执行模型

HTTP 网关落地后，job 系统采用文件状态目录，不引入外部队列：

- `.runtime/ops/jobs/<job_id>.json`
- `.runtime/ops/logs/<job_id>.log`
- `.runtime/ops/queue/`
- `.runtime/ops/locks/`

状态流转：

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

锁模型：

- 单机单 deploy 锁
- `service`、`smoke`、`logs` 可根据动作粒度选择共享锁或只读执行

执行模型：

- `webhook/main.py` 只负责鉴权和入队，不直接执行业务动作
- 每次成功入队后，网关尝试启动一次 `bash scripts/opsctl.sh run-next-job`
- `run-next-job` 先获取全局 runner 锁，再从队列目录按 FIFO 取第一个 job
- 若锁已被占用，当前触发直接返回，避免并发 runner
- runner 在一个进程内持续消费，直到队列为空

恢复策略：

- job 文件中记录 `heartbeat_at`
- runner 每个关键阶段更新一次 heartbeat
- 网关启动时执行一次 `doctor --recover-jobs`
- 若发现 `running` job 超过阈值无 heartbeat，则标记为 `failed`，并写入 `result_reason=orphaned`
- 若发现 deploy job 在 `queued` 阶段与已有同分支 deploy 重复，则只保留最新 ref，旧 job 标记为 `cancelled`，并写入 `result_reason=superseded`

去重规则：

- 同一分支的 deploy job 只能同时存在一个 `running` 和一个 `queued`
- 新的 deploy 到来时，如果已有同分支 `queued` job，则先把旧 job 标记为 `cancelled` 且 `result_reason=superseded`，再创建新的 job_id 入队
- 非 deploy job 默认不做合并

## 8. 生产服务模型

### 8.1 生产

生产统一走 `systemd`：

- `trade-arena-backend.service`
- `trade-arena-frontend.service`
- `trade-arena-ops-gateway.service`

运行身份与权限边界：

- backend、frontend、ops-gateway 三个服务统一以同一个非 root 系统用户运行，例如 `tradearena`
- Nginx 继续作为公网入口，代理到 `127.0.0.1:3000` 与 `127.0.0.1:9000`
- ops-gateway 不直接持有 root shell 权限
- 需要访问 `systemctl` / `journalctl` 时，只能调用受限包装器

受限包装器：

- 新增 root 拥有的包装器，例如 `/usr/local/bin/trade-arena-systemctl`
- 包装器是生产环境唯一允许的服务控制入口
- `scripts/ops/service.sh` 在生产环境只能通过 `sudo -n /usr/local/bin/trade-arena-systemctl ...` 调用它
- 禁止在生产环境直接调用原生 `systemctl`
- 通过 `/etc/sudoers.d/trade-arena-ops` 向 `tradearena` 用户授予该包装器的无密码执行权限
- 包装器只允许固定白名单：
  - `restart trade-arena-backend.service`
  - `restart trade-arena-frontend.service`
  - `restart trade-arena-ops-gateway.service`
  - `status trade-arena-backend.service`
  - `status trade-arena-frontend.service`
  - `status trade-arena-ops-gateway.service`
  - `journalctl -u trade-arena-backend.service -n <tail>`
  - `journalctl -u trade-arena-frontend.service -n <tail>`
  - `journalctl -u trade-arena-ops-gateway.service -n <tail>`
- `trade-arena-ops-gateway.service` 不允许通过 HTTP 触发自重启
- `target=all` 不作为第一阶段远程动作

这样处理的原因：

- 避免把网关做成隐形 root
- 避免“重启自己”导致 job 失托管
- 保留生产环境日志与服务控制能力，但边界清楚

`scripts/ops/service.sh` 作为统一适配层：

- 生产模式只调用受限包装器
- 本地模式调用 `scripts/service_ctl.sh`

`/ops/status` 与 `/ops/logs?scope=gateway` 的读取规则：

- 远程读 gateway 状态时，优先返回当前进程自报健康状态与最近 runner 摘要
- 远程读 gateway 日志时，返回网关写入的应用日志文件，不直接开放任意 `journalctl`
- 本地 CLI 深度排障时，可通过受限包装器读取 gateway 的 `systemd` 状态与 `journalctl`

### 8.1.1 网关自身升级生效路径

第一阶段采用“代码部署与网关切换分离”的办法：

- 常规 `deploy` job 只负责 backend/frontend 与构建产物
- 若变更涉及下列路径，则 deploy 结果里标记 `gateway_reload_required=true`
  - `webhook/**`
  - `scripts/opsctl.sh`
  - `scripts/ops/**`
- 网关本身不通过 HTTP 触发自重启
- 运维人员在确认队列为空后，本地执行：

```bash
bash scripts/opsctl.sh gateway-reload
```

`gateway-reload` 的硬约束：

- 发现 `queued` 或 `running` job 时拒绝执行
- 先写入维护标记，再通过受限包装器重启 `trade-arena-ops-gateway.service`
- 重启后启动过程自动执行一次 `doctor --recover-jobs`

这样做的原因：

- 避免运行中的 gateway 杀死自己，导致 job 失托管
- 保持第一阶段实现简单可靠
- 把“gateway 代码升级”明确成单独动作，而不是隐含在普通 deploy 里

### 8.2 本地与测试机

保留：

- `scripts/service_ctl.sh`
- `scripts/dev_self_check.sh`
- `scripts/online_regression.sh`

但它们会被纳入 `opsctl` 命令面，不再和部署脚本并行演化。

## 9. 配置与密钥设计

新增配置项：

- `OPS_ENV=local|staging|prod`
- `OPS_ALLOWED_BRANCHES=main`
- `OPS_API_KEY=...`
- `WEBHOOK_SECRET=...`
- `OPS_RUNTIME_DIR=.runtime/ops`
- `OPS_LOG_DIR=.runtime/ops/logs`
- `OPS_NOTIFY_URL=...`
- `OPS_PROJECT_ROOT=/opt/trade-arena`
- `OPS_SERVICE_DRIVER=systemd|pidfile`

规则：

- `OPS_API_KEY` 与 `WEBHOOK_SECRET` 均不得有默认值
- 缺失时生产服务拒绝启动
- `deploy.sh` 不再自行内嵌路径和常量
- `OPS_ENV=local` 时允许省略 `OPS_API_KEY`，但只用于 `127.0.0.1` 联调
- 生产和 staging 禁止省略密钥

## 10. 日志与审计

日志分三类：

1. 网关访问日志
2. job 执行日志
3. 事件摘要日志

要求：

- 每个 job 必须有 `job_id`
- 每条写操作必须记录 `source`
- 日志默认脱敏邮箱、token、secret、Authorization
- `webhook/DEPLOY_LOG.md` 可保留为面向人读的摘要视图，但不再作为唯一状态源

## 11. 文档与 AGENTS 改造

### 11.1 新增文档

- `docs/ops-automation-manual.md`

内容包括：

- 唯一入口
- CLI 命令面
- HTTP API
- 密钥要求
- 生产部署模型
- 回滚与排障
- 人类和 Agent 的共同约束

### 11.2 需要同步更新的文档

- `docs/README.md`
- `docs/ops-reference-manual.md`
- `docs/cloud-deployment-guide.md`
- `docs/ops-runbook-local-development-and-test-server.md`
- `docs/testing-process-manual.md`
- `docs/testing-checklist.md`
- `AGENTS.md`

### 11.3 AGENTS.md 需要新增的硬约束

- 运维入口统一为 `scripts/opsctl.sh`
- 不得直接调用 `webhook/deploy.sh`
- 不得在生产场景直接 `pkill` / `nohup`
- 不得把任意脚本直接暴露为公网 HTTP
- 运维 HTTP 只允许白名单动作
- 生产密钥不得使用默认值

### 11.4 迁移兼容规则

- 第一阶段保留旧入口 `POST /webhook`，并把它内部转发到新处理器
- 新入口 `POST /hooks/github/push` 与旧入口并存一个迁移周期
- GitHub Webhook 配置切流前，旧入口不得移除
- `scripts/service_ctl.sh` 仍可用来本地拉起 webhook/gateway
- 当 `START_WEBHOOK=1` 且 `OPS_ENV=local` 时，允许无 `OPS_API_KEY` 启动
- 所有入口切换和手册更新必须在同一批改动中完成，不能把文档更新延后到最后

## 12. 实施阶段

### 阶段 1：统一脚本入口与安全收口

- 新增 `scripts/opsctl.sh`
- 把 `deploy.sh` 改成薄编排器
- 移除默认 `WEBHOOK_SECRET`
- 给日志接口加鉴权
- 加入 branch allowlist
- 同步更新 `docs/README.md`、`docs/ops-reference-manual.md`、`AGENTS.md` 的入口描述
- 保留 `/webhook` 兼容入口
- 这一阶段仍允许沿用旧的单 deploy 锁与 pending 机制，先完成入口收口和安全收口

### 阶段 2：HTTP 网关与 job 系统

- 扩展 `webhook/main.py`
- 增加 job 状态目录与日志目录
- 实现 `deploy/service/migrate/smoke/status/logs`
- 实现 runner 锁、heartbeat 恢复、deploy 去重

### 阶段 3：CI 与文档收口

- 新增 `.github/workflows/ci.yml`
- 更新部署与运维文档
- 更新 `AGENTS.md`

## 13. 验收标准

满足以下条件才算完成：

- 所有运维动作都能从 `scripts/opsctl.sh` 调起
- GitHub push 与人工 HTTP 调用都走同一 job 执行链
- 生产部署不再直接使用 `pkill` / `nohup` / `uvicorn --reload`
- `OPS_API_KEY` 与 `WEBHOOK_SECRET` 无默认值
- 日志接口必须鉴权且默认脱敏
- job 队列具备可恢复性，网关重启后不会留下永久 `running`
- 远程动作不包含 `rollback` 与 `restart webhook/all`
- CI 能稳定跑后端测试和前端 build
- 文档与 `AGENTS.md` 明确写清统一入口和禁令

## 14. 测试策略

实现阶段至少覆盖：

- `opsctl` 参数解析与退出码测试
- gateway 鉴权测试
- branch allowlist 测试
- job 状态流转测试
- 日志脱敏测试
- 本地 smoke 测试
- 生产 profile 的 deploy dry-run 或 staging 测试

## 15. 风险与取舍

### 15.1 风险

- 生产切换到 `systemd` 时需要和现有服务器状态对齐
- 旧脚本依赖硬编码路径，改造时要避免一次性切断线上
- job 文件队列虽然简单，但需要保证锁与恢复逻辑可靠
- 若未来要开放 rollback，必须先建立 migration 兼容判定机制

### 15.2 取舍

本设计选择：

- 先做单机可靠收口，再考虑多机
- 先做白名单运维协议，再考虑更强签名体系
- 先做最小 CI，再考虑更完整 release pipeline
- 先禁止危险远程动作，再按能力成熟度逐步开放

## 16. 实现入口建议

实现从下面顺序开始：

1. `scripts/opsctl.sh`
2. `scripts/ops/lib/*.sh`
3. `scripts/ops/deploy.sh`
4. `webhook/main.py` 网关扩展
5. `webhook/config.py` 密钥与配置收口
6. `.github/workflows/ci.yml`
7. 文档与 `AGENTS.md`

## 17. 回滚原则

第一阶段正式回滚策略保持与现有运维手册一致：

- 默认只允许“提交回滚 + 再部署”
- 不开放远程 `rollback` HTTP 动作
- 第一阶段不提供 `opsctl rollback` 自动化能力
- 不提供“任意 ref 直接切回去”的自动化能力

只有在未来同时满足以下条件时，才考虑开放受限 rollback：

- 后端迁移具备明确 downgrade 脚本
- deploy 清单能判断代码版本与 migration 版本兼容性
- 回滚前能做自动风险拦截
- 回滚动作可以区分“代码回滚”和“数据库回滚”
