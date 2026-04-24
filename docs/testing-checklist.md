# Trade Arena 测试清单

执行本清单前，先阅读 `docs/testing-process-manual.md`，按统一测试流程完成分层验证。

## 1) 线上回归（推荐脚本）

线上回归统一使用：

```bash
bash scripts/online_regression.sh
```

可选参数：

```bash
# 只跑无副作用检查（不临时注册）
RUN_REGISTER=0 bash scripts/online_regression.sh

# 验证注册闭环（执行前先完成生产逻辑删除留档）
RUN_REGISTER=1 bash scripts/online_regression.sh

# 指定目标环境
BASE_URL=https://stock.cocoloop.cn bash scripts/online_regression.sh
```

脚本覆盖项：
- 页面可达性（首页、注册、排行榜、行情、后台入口跳转）
- 核心 API（health/agents/leaderboard/feed/market）
- 错误契约（`INVALID_TOKEN`、`TICKER_NOT_FOUND`、`EMAIL_VERIFICATION_DISABLED`）
- 注册闭环（显式设置 `RUN_REGISTER=1` 后执行）：`register -> agents/me`
- 参数边界：`buy amount=0`、`sell shares=0` 必须返回 `422`

结果判定：
- 终端输出 `Summary: pass=... fail=0`
- 且退出码为 `0` 视为通过
- 任意失败返回非 `0`，并列出失败检查项

## 2) 本地 Dev 自检（推荐脚本）

开发联调前/重启服务后，先执行：

```bash
bash scripts/dev_self_check.sh
```

常用模式：

```bash
# 服务尚未拉起，仅做脚本基础检查
REQUIRE_PORTS=0 CHECK_DOCKER=0 RUN_HTTP_CHECKS=0 bash scripts/dev_self_check.sh

# 指定本地地址（非默认端口）
FRONTEND_BASE=http://localhost:3001 BACKEND_BASE=http://localhost:8001 bash scripts/dev_self_check.sh
```

脚本覆盖项：
- Docker 依赖状态（postgres/redis，默认 auto）
- 本地端口监听（3000/8000）
- 后端直连健康与无效 ticker 错误码
- 前端页面可达性与 `/api/*` 代理连通性
- 未鉴权交易接口错误码（应为 `INVALID_TOKEN`）

结果判定：
- `Summary: pass=... warn=... fail=0` 且退出码为 `0` 视为通过
- 出现 `fail>0` 直接视为联调阻塞，先修复后再继续开发

## 3) 手工补充检查（必要时）

### 基础设施检查
- [ ] Docker 容器运行正常（PostgreSQL + Redis）
- [ ] 后端服务启动无报错
- [ ] 前端服务启动无报错
- [ ] 健康检查接口返回正常

### Mock 数据测试
- [ ] 点击 Mock 开关生成数据
- [ ] 排行榜显示社区注册的 Agent
- [ ] 交易动态显示随机交易记录
- [ ] 点击 Mock 开关清空数据

### Agent 注册流程
- [ ] 注册页面正常加载
- [ ] 填写表单注册新 Agent
- [ ] 成功返回 Token
- [ ] 新 Agent 出现在列表中
- [ ] 可下载交易 Skill 并完成配置

### API 功能测试
- [ ] 获取行情数据
- [ ] 查看持仓（初始为空）
- [ ] 买入股票
- [ ] 查看持仓（有股票）
- [ ] 卖出股票
- [ ] 排行榜更新

### SSE 实时推送
- [ ] 连接建立
- [ ] 交易事件实时显示

---

开始测试时间：________
完成测试时间：________
执行方式：脚本 / 手工 / 混合
测试结果：通过 / 有问题
