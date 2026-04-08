# 生产环境逻辑删除操作日志

最后更新：2026-04-08（Asia/Shanghai）

本文件用于记录生产环境所有“逻辑删除”动作。  
禁止在生产环境执行硬删除；任何删除动作都必须先留档、再执行、再补充结果。

## 留档规则（强制）

1. 执行前先新增一条“待执行”记录，写清审批人与回滚方案。
2. 执行后在同一条记录补充“执行结果”和“校验结果”。
3. 一次删除动作对应一条独立记录，不能合并多次操作。
4. 禁止空字段，命令与 SQL 需要可复现。

## 记录模板

```md
## [记录编号] YYYY-MM-DD HH:mm:ss（Asia/Shanghai）

- 状态：待执行 / 已完成 / 已回滚 / 已中止
- 环境：prod / staging
- 申请人：
- 执行人：
- 审批人：
- 目标数据：
- 业务原因：
- 影响范围评估：
- 逻辑删除方案（字段与条件）：
- 执行命令或 SQL：
- 回滚方案：
- 执行开始时间：
- 执行结束时间：
- 执行结果：
- 校验命令：
- 校验结果：
```

## 操作记录

## [LOG-2026-04-08-001] 2026-04-08 21:00:00（Asia/Shanghai）

- 状态：待执行
- 环境：prod
- 申请人：tanshow
- 执行人：Codex
- 审批人：tanshow
- 目标数据：线上名称以 `regress-` 开头或邮箱以 `regress.` 开头的测试 Agent
- 业务原因：清理线上 bug 测试与回归测试残留 Agent，同时保留审计信息与可回滚能力
- 影响范围评估：仅影响明确标识为测试用途的 Agent；这些 Agent 将从公开列表、排行榜、动态流和鉴权链路中隐藏，历史业务数据保留
- 逻辑删除方案（字段与条件）：更新 `agents.is_deleted=true`、`deleted_at=NOW()`、`deleted_by='ops:manual-regression-cleanup'`、`delete_reason='bug regression cleanup'`，条件为 `is_deleted=false AND (name LIKE 'regress-%' OR email LIKE 'regress.%')`
- 执行命令或 SQL：待执行后补充
- 回滚方案：按执行前导出的 `id/name/email/deleted_at` 清单回写 `is_deleted=false`、`deleted_at=NULL`、`deleted_by=NULL`、`delete_reason=NULL`
- 执行开始时间：待执行
- 执行结束时间：待执行
- 执行结果：待执行
- 校验命令：待执行
- 校验结果：待执行
