# Trade Arena 下一位 Agent 交接文档（2026-03-19）

> 用途：给下一位接手的 agent 快速理解当前状态、已做修改、剩余问题和建议切入点。

## 1. 本轮已经完成的事情

- 确认本地后端 `8000` 在运行，健康检查正常。
- 确认本地前端 `3000` 在浏览器中可打开。
- 识别出 shell 代理变量会让 `curl localhost:3000` 误报 `502`。
- 将前端 API 透传改成 Nuxt 服务端路由实现：
  - `frontend/server/api/[...path].ts`
- 去掉了 `frontend/nuxt.config.ts` 里那套不再需要的 API 代理配置。
- 新增两份交付文档：
  - `docs/ops-runbook-local-development-and-test-server.md`
  - `docs/handoff-next-agent-2026-03-19-current-state-and-next-steps.md`

## 2. 当前系统状态

### 后端

验证命令：

```bash
curl --noproxy '*' -sS http://localhost:8000/api/health | python3 -m json.tool
```

当前结果：

```json
{
  "status": "ok",
  "db": true,
  "redis": true
}
```

### 测试数据

验证命令：

```bash
curl --noproxy '*' -sS http://localhost:8000/api/dev/status | python3 -m json.tool
```

当前结果：

```json
{
  "has_data": true,
  "agents": 4,
  "trades": 27
}
```

### 前端

- 浏览器可访问：`http://localhost:3000`
- 命令行验证必须绕过代理：

```bash
curl --noproxy '*' -sS http://localhost:3000/
```

## 3. 当前最重要的事实

不要把下面的问题误判成服务不可用：

- `/api/market/overview` 返回真实数据
- 但 `/market` 页面仍然渲染成 0 / 空态

这说明核心问题在前端页面实现，不在后端接口。

## 4. 建议下一位 Agent 优先处理的任务

### 任务 1：修复市场总览页数据不显示

现象：

- `/market` 页面桌面端和移动端都能打开
- 但美股 / A 股概览卡片是 `0`
- API 本身有数据

优先看：

- `frontend/pages/market.vue`

重点关注：

- `overviewData` 的初始化与缓存读取
- `onMounted` 后客户端 `$fetch`
- `marketSections` 对 `overviewData.value.markets` 的依赖
- 是否存在 hydration / client-only 状态覆盖问题

### 任务 2：修复移动端导航

现象：

- 窄视口下品牌名和导航文字被挤成纵向排列
- CTA 按钮挤在右上角，首屏观感很差

优先看：

- `frontend/app.vue`

### 任务 3：统一涨跌色语义

现象：

- 项目支持 `useColorConvention()`
- 但 Agent 详情页仍有硬编码红绿

优先看：

- `frontend/pages/agent/[id].vue`

### 任务 4：提高弱文本可读性

现象：

- `10px` / `11px` 配合很浅的灰色，在白底上读起来偏吃力

优先看：

- `frontend/assets/css/main.css`

## 5. 本轮 UI 审查结论摘要

### 高优先级问题

- 移动端导航不可用。
- 市场总览页展示结果与接口数据不一致。

### 中优先级问题

- 涨跌色切换没有在所有页面保持一致。
- 全站次级文字对比度偏低。
- 导航版心和正文版心不一致，桌面端看起来像两套布局拼接。

## 6. 当前相关文件

- `frontend/app.vue`
- `frontend/assets/css/main.css`
- `frontend/pages/market.vue`
- `frontend/pages/agent/[id].vue`
- `frontend/nuxt.config.ts`
- `frontend/server/api/[...path].ts`

## 7. 工作区情况

当前仓库是脏工作区，已经有很多未提交改动，不要直接做整仓回滚。

开始改动前先看：

```bash
git status --short
```

原则：

- 只改你负责的问题。
- 不要回退你没做的改动。
- 如果要修 UI，优先在前端目录内收口。

## 8. 复核命令

### 后端健康

```bash
curl --noproxy '*' -sS http://localhost:8000/api/health | python3 -m json.tool
```

### 市场总览 API

```bash
curl --noproxy '*' -sS http://localhost:3000/api/market/overview | python3 -m json.tool | sed -n '1,40p'
```

### 排行榜 API

```bash
curl --noproxy '*' -sS 'http://localhost:3000/api/leaderboard?market=overall' | python3 -m json.tool | sed -n '1,40p'
```

### 打开前端

```bash
open http://localhost:3000
```
