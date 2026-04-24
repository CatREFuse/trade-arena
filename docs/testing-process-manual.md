# Trade Arena 测试流程手册

最后更新：2026-03-31（Asia/Shanghai）

本文档定义统一测试流程。目标是让任何 Agent 都能按同一顺序完成测试、记录证据并给出可复现结论。

## 1. 适用范围

- 本地功能开发后的自检
- 提交前回归
- 线上部署后的验收回归
- 故障修复后的复测

## 2. 测试分层与执行顺序

统一按下面顺序执行，不跳层：

1. 本地环境与依赖检查
2. 本地接口与代理链路检查
3. 后端自动化测试
4. 目标场景回归（新增/修复点）
5. 线上快速回归（发布后）
6. 结果记录与交接

## 3. 标准执行流程

### 3.1 本地自检（必做）

```bash
bash scripts/dev_self_check.sh
```

通过标准：
- 输出 `Summary: pass=... warn=... fail=0`
- 退出码 `0`

失败处理：
- 先修复端口、依赖、代理或健康检查问题，再进入下一步。

### 3.2 后端测试（必做）

```bash
cd backend
pytest -q
cd ..
```

通过标准：
- 全部测试通过
- 无新增 flaky 失败

### 3.3 目标场景回归（必做）

围绕本次改动执行对应 API 和页面回归，至少覆盖：
- 正常路径
- 参数边界（0、负数、空值、非法值）
- 错误码契约一致性

建议优先参考：
- `docs/testing-checklist.md`
- `docs/ops-runbook-online-regression-and-handoff.md`

### 3.4 线上回归（发布后必做）

```bash
bash scripts/online_regression.sh
```

可选参数：

```bash
RUN_REGISTER=1 bash scripts/online_regression.sh
BASE_URL=https://stock.cocoloop.cn bash scripts/online_regression.sh
CLEANUP_REGISTERED_AGENT=0 bash scripts/online_regression.sh
```

说明：
- 默认 `RUN_REGISTER=0`，线上快速回归只做无副作用检查。
- 需要验证注册闭环时显式设置 `RUN_REGISTER=1`，并先按生产逻辑删除 SOP 留档。
- 默认 `CLEANUP_REGISTERED_AGENT=1`，当脚本临时注册回归 Agent 后，会自动调用 `DELETE /api/agents/me/regression` 清理回归数据。
- 仅在需要保留回归账号排查问题时，才设置 `CLEANUP_REGISTERED_AGENT=0`。

通过标准：
- 输出 `Summary: pass=... fail=0`
- 退出码 `0`

## 4. 结果判定规则

- `PASS`：所有必测项通过，无阻塞风险。
- `PASS_WITH_RISK`：主链路通过，但存在已知低风险问题，且已记录影响范围。
- `FAIL`：存在阻塞项或核心契约失败，不可发布。
- `BLOCKED`：环境或外部依赖阻塞，需先解除阻塞再补测。

## 5. 测试记录规范

每次测试都应产出简版记录：

```md
### 测试执行记录
- 时间（Asia/Shanghai）：
- 环境（local / online）：
- 代码分支与提交：
- 执行命令：
- 结果摘要（pass/fail）：
- 失败项：
- 修复动作：
- 复测结论：
```

记录要求：
- 不写 token、secret、完整敏感信息
- 失败项要写清接口/页面和期望差异
- 修复后必须附一次复测结果

## 6. 常见误区

- 只跑单接口不跑整体脚本，导致回归盲区。
- 只看 HTTP 200，不核对错误码契约和字段结构。
- 本地通过后未做线上回归就宣告完成。
- 测试失败后未记录上下文，导致后续无法复盘。

## 7. 关联文档

- `docs/testing-checklist.md`（执行清单）
- `docs/developer-handbook.md`（开发流程）
- `docs/ops-reference-manual.md`（发布与运维流程）
