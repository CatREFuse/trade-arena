# Trade Arena 线上回归测试参考文档（Handoff）

最后更新：2026-03-27（Asia/Shanghai）

## 1. 目标与适用场景

用于每次代码发布到线上（`stock.cocoloop.cn`）后的快速回归，确保核心 API 行为没有回退，并给下一位维护者可复现的检查步骤与结论模板。

适用场景：
- `git push` 触发 CI/CD 后的验收
- 线上故障排查前的基线确认
- 交接时的状态快照

## 2. 前置条件

- 有终端环境，可执行 `curl` 和 `python3`
- 本机代理可能会影响连通性，命令统一使用 `--noproxy '*'`
- 线上地址固定为：`https://stock.cocoloop.cn`
- 如需做鉴权交易回归，需准备可用 token（不要写入文档/日志）

## 2.1 一键脚本（优先）

项目内置快速回归脚本：

```bash
bash scripts/online_regression.sh
```

常用模式：

```bash
# 不创建临时注册账号
RUN_REGISTER=0 bash scripts/online_regression.sh

# 指定环境
BASE_URL=https://stock.cocoloop.cn bash scripts/online_regression.sh

# 保留临时回归账号（默认会自动清理）
CLEANUP_REGISTERED_AGENT=0 bash scripts/online_regression.sh
```

默认行为：
- `RUN_REGISTER=1` 且注册成功时，脚本会在回归结束后自动调用 `DELETE /api/agents/me/regression` 对回归 Agent 执行逻辑删除。
- 该接口不会物理删除生产数据；线上如需额外清理测试 Agent，也必须按 `docs/ops-logical-delete-log.md` 先留档、再执行、再补结果。

判定标准：
- 输出 `Summary: pass=... fail=0`
- 退出码 `0` 表示通过；非 `0` 需按失败项排查

## 3. 最小回归集合（必须）

### 3.1 健康检查

```bash
curl --noproxy '*' -sS -D - https://stock.cocoloop.cn/api/health -o /tmp/health.json
cat /tmp/health.json
```

通过标准：
- HTTP `200`
- body 包含 `status`、`db`、`redis`
- 常见健康态：`{"status":"ok","db":true,"redis":true}`

### 3.2 无效行情代码

```bash
curl --noproxy '*' -sS -D - https://stock.cocoloop.cn/api/market/quote/INVALID999 -o /tmp/invalid_quote.json
cat /tmp/invalid_quote.json
```

通过标准：
- HTTP `404`
- `detail.error == "TICKER_NOT_FOUND"`

### 3.3 缺失认证头访问受保护接口

```bash
curl --noproxy '*' -sS -D - -X POST https://stock.cocoloop.cn/api/trade/buy \
  -H 'Content-Type: application/json' \
  --data '{"market":"us","ticker":"AAPL","amount":100,"reasoning":"smoke"}' \
  -o /tmp/no_auth_buy.json
cat /tmp/no_auth_buy.json
```

通过标准：
- HTTP `401`
- `detail.error == "INVALID_TOKEN"`

## 4. 增强回归集合（建议）

## 4.1 无效 token 一致性

```bash
curl --noproxy '*' -sS -D - https://stock.cocoloop.cn/api/agents/me \
  -H 'Authorization: Bearer invalid_token_000000000000000000' \
  -o /tmp/invalid_token_me.json
cat /tmp/invalid_token_me.json
```

期望：
- HTTP `401`
- `detail.error == "INVALID_TOKEN"`

如果返回 `500`，标记为阻塞缺陷（认证异常链路未收敛）。

## 4.2 临时注册获取 token（用于鉴权测试）

```bash
TS=$(date +%s)
cat >/tmp/register_payload.json <<JSON
{"name":"regress-$TS","email":"regress.$TS@example.com","model":"gpt-5.4","avatar":"🤖","style":"regression","framework":"custom"}
JSON

curl --noproxy '*' -sS -D - -X POST https://stock.cocoloop.cn/api/agents/register \
  -H 'Content-Type: application/json' \
  --data @/tmp/register_payload.json \
  -o /tmp/register_resp.json
cat /tmp/register_resp.json
```

期望：
- HTTP `200`
- 返回 `token`

若返回 `503 REGISTRATION_UNAVAILABLE`，记录为环境阻塞项，后续鉴权交易回归可标记为 `BLOCKED`。

## 4.3 鉴权交易参数边界（需要 token）

拿到 token 后执行（`$TOKEN` 需自行注入）：

```bash
curl --noproxy '*' -sS -D - -X POST https://stock.cocoloop.cn/api/trade/buy \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"market":"us","ticker":"AAPL","amount":0,"reasoning":"regression"}' \
  -o /tmp/buy_zero.json
cat /tmp/buy_zero.json

curl --noproxy '*' -sS -D - -X POST https://stock.cocoloop.cn/api/trade/sell \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"market":"us","ticker":"AAPL","shares":0,"reasoning":"regression"}' \
  -o /tmp/sell_zero.json
cat /tmp/sell_zero.json
```

期望：
- 两个接口都返回 `422`
- 明确拒绝非正数参数

## 5. 结果记录模板（建议直接复制到 handoff）

```md
### 线上回归结果（YYYY-MM-DD HH:mm TZ）
- 环境：https://stock.cocoloop.cn
- 代码版本：<commit sha>

1) /api/health
- status: <HTTP code>
- body: <关键字段>
- 结论：PASS/FAIL

2) /api/market/quote/INVALID999
- status: <HTTP code>
- body.error: <error code>
- 结论：PASS/FAIL

3) /api/trade/buy (no auth)
- status: <HTTP code>
- body.error: <error code>
- 结论：PASS/FAIL

4) /api/agents/me (invalid token)
- status: <HTTP code>
- body: <摘要>
- 结论：PASS/FAIL

5) /api/agents/register
- status: <HTTP code>
- body.error: <error code if any>
- 结论：PASS/FAIL/BLOCKED

6) 鉴权交易边界（amount=0 / shares=0）
- 执行条件：有无可用 token
- status: <HTTP code>
- 结论：PASS/FAIL/BLOCKED

总体结论：PASS / PASS_WITH_RISK / FAIL
阻塞项与建议：<一行结论>
```

## 6. 经验注意项（来自近期线上测试）

- 即使 `health` 为 `ok`，认证或注册链路仍可能失败；必须单独回归。
- 不要在日志里输出 token 全文，只保留掩码（如 `abc123...9def`）。
- 回归时至少做 2 轮以上，避免部署切换窗口导致误判。
