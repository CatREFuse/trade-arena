# Trade Arena 本期 Dev 服务器小队测试记录

最后更新：2026-03-31（Asia/Shanghai）

## 1. 目标

本期目标是完成以下工作：

1. 启动一套可用的本地 dev 服务（frontend + backend）。
2. 以小队并行方式执行基础自检、自动化测试、回归测试。
3. 形成可复用的测试记录，便于后续交接和复测。

## 2. 环境信息

- 执行时间：2026-03-31 13:08:16 CST
- 分支：`main`
- 提交：`ae4a111`
- 项目目录：`/Users/tanshow/Developer/trade-arena`

## 3. Dev 服务器启动记录

标准启动命令：

```bash
MODE=dev START_DOCKER=1 BUILD_FRONTEND=0 bash scripts/service_ctl.sh start
```

本机实际执行：

```bash
MODE=dev START_DOCKER=0 BUILD_FRONTEND=0 bash scripts/service_ctl.sh start
```

说明：

- 当前环境缺少 `docker` 命令，标准命令无法直接启动容器依赖。
- 使用同一脚本的降级模式启动成功，backend/frontend 健康检查均通过。
- 在本执行环境中，普通命令结束后后台进程会被回收。最终采用持久 TTY 会话保活，保证测试期间服务持续可用。

启动结果：

- Backend 健康检查：`http://127.0.0.1:8000/api/health` 通过
- Frontend 健康检查：`http://127.0.0.1:3000/` 通过

## 4. 小队分工

- A 组：本地自检与服务状态核验
  - `bash scripts/dev_self_check.sh`
  - `bash scripts/service_ctl.sh status`
- B 组：后端自动化测试
  - `cd backend && pytest -q`
- C 组：回归脚本与运维脚本自检
  - `RUN_REGISTER=0 BASE_URL=http://127.0.0.1:3000 bash scripts/online_regression.sh`
  - `bash scripts/opsctl.sh doctor`

## 5. 小队执行结果

### A 组结果

- 状态：PASS
- 摘要：
  - `bash scripts/dev_self_check.sh`：`pass=9 warn=1 fail=0`
  - `bash scripts/service_ctl.sh status`：backend/frontend 运行中，webhook 停止（本期未纳入 dev 测试）
- 备注：
  - A 组首轮在“服务未保活”条件下执行失败。
  - 固定保活方式后复测通过，结论以复测结果为准。

### B 组结果

- 状态：PASS
- 摘要：
  - `cd backend && pytest -q`：`52 passed in 11.96s`
- 备注：
  - 小队并行结果与主线程复测一致，未发现 flaky 失败。

### C 组结果

- 状态：PASS
- 摘要：
  - `RUN_REGISTER=0 BASE_URL=http://127.0.0.1:3000 bash scripts/online_regression.sh`：`pass=20 fail=0`
  - `bash scripts/opsctl.sh doctor`：通过（`doctor checks passed`）
- 备注：
  - C 组首轮在“服务未保活”条件下全量失败。
  - 固定保活方式后复测通过，结论以复测结果为准。

## 6. 总结与后续动作

- 总体判定：PASS
- 风险项：
  - 当前执行环境未安装 docker，依赖容器未在本期用标准路径拉起。
  - 若要在同一执行环境复现，建议在持久 TTY 中启动服务后再跑脚本测试。
- 后续动作：
  - 在具备 docker 的主机上补跑一轮 `START_DOCKER=1` 的同口径测试。
  - 继续沿用本小队分工执行后续迭代测试，减少串行等待。

## 7. 测试执行记录

- 开始时间（Asia/Shanghai）：2026-03-31 13:08:16 CST
- 结束时间（Asia/Shanghai）：2026-03-31 13:13:17 CST
- 环境：local dev
- 执行方式：脚本 + 小队并行 + 主线程复测
