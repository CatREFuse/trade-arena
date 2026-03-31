# Trade Arena 本地开发与测试服务器运维手册

> 用途：给维护本地开发环境、排查服务可用性、重启测试服务器的人看。

## 1. 当前默认端口

- 前端：`http://localhost:3000`
- 后端：`http://localhost:8000`
- PostgreSQL：`localhost:5432`
- Redis：`localhost:6379`

## 2. 当前已知运行方式

### 后端

在 `backend/` 目录启动：

```bash
uvicorn app.main:app --reload --port 8000
```

健康检查：

```bash
curl --noproxy '*' -sS http://localhost:8000/api/health | python3 -m json.tool
```

期望结果：

```json
{
  "status": "ok",
  "db": true,
  "redis": true
}
```

### 前端

在 `frontend/` 目录启动：

```bash
npm run dev
```

浏览器访问：

```bash
http://localhost:3000
```

## 3. 一定要注意的代理坑

当前 shell 环境存在下面这些代理变量：

- `http_proxy=http://127.0.0.1:17890`
- `https_proxy=http://127.0.0.1:17890`
- `all_proxy=socks5://127.0.0.1:17890`

这会导致直接用 `curl http://localhost:3000/...` 时，可能误收到 `502 Bad Gateway`，看起来像前端挂了，实际上浏览器页面仍然是正常的。

排查本地服务时，统一这样写：

```bash
curl --noproxy '*' -sS http://localhost:3000/
curl --noproxy '*' -sS http://localhost:3000/api/health
curl --noproxy '*' -sS 'http://localhost:3000/api/leaderboard?market=overall'
```

## 4. 前端 API 代理实现

当前前端不再依赖 `nuxt.config.ts` 里的 Nitro `devProxy` / `routeRules`。

实际代理入口是：

- `frontend/server/api/[...path].ts`

作用：

- 浏览器请求 `http://localhost:3000/api/*`
- Nuxt 服务端把请求转发到 `http://127.0.0.1:8000/*`

如果你后面要改后端地址，优先改这个文件。

## 5. 启停与排查命令

### 查看端口占用

```bash
lsof -nP -iTCP:3000 -sTCP:LISTEN
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

### 杀掉前端开发服务

```bash
lsof -tiTCP:3000 -sTCP:LISTEN | xargs -r kill
```

### 杀掉后端开发服务

```bash
lsof -tiTCP:8000 -sTCP:LISTEN | xargs -r kill
```

### 重启前端

```bash
cd frontend
npm run dev
```

### 重启后端

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

## 5.1 一键 Dev 自检脚本（推荐）

项目内置开发态自检脚本，默认检查本地 `3000/8000`：

```bash
bash scripts/dev_self_check.sh
```

常用参数：

```bash
# 不检查 docker / 端口 / HTTP（仅验证脚本可执行）
REQUIRE_PORTS=0 CHECK_DOCKER=0 RUN_HTTP_CHECKS=0 bash scripts/dev_self_check.sh

# 非默认端口
FRONTEND_BASE=http://localhost:3001 BACKEND_BASE=http://localhost:8001 bash scripts/dev_self_check.sh
```

通过标准：
- 输出 `Summary: pass=... warn=... fail=0`
- 退出码为 `0`

## 6. 数据与 Mock 状态

当前可以通过后端开发接口检查是否已有测试数据：

```bash
curl --noproxy '*' -sS http://localhost:8000/api/dev/status | python3 -m json.tool
```

本次记录时的结果是：

```json
{
  "has_data": true,
  "agents": 4,
  "trades": 27
}
```

### 生成测试数据

```bash
curl --noproxy '*' -X POST http://localhost:8000/api/dev/mock
```

### 清空测试数据

```bash
curl --noproxy '*' -X POST http://localhost:8000/api/dev/reset
```

## 7. 当前已知服务层面结论

- 后端健康状态正常，数据库和 Redis 都可用。
- 前端开发服务器可在浏览器中打开。
- 前端 API 透传链路可用，但命令行验证必须绕过本机代理。

## 8. 当前不是“服务挂了”，而是“前端页面实现有 bug”的问题

下面这个现象很重要，避免误判成接口故障：

- `GET /api/market/overview` 有真实数据
- 但 `/market` 页面仍然显示全 0 和空态卡片

这属于前端页面实现问题，不是后端挂了。

优先排查文件：

- `frontend/pages/market.vue`

## 9. 如果需要给局域网设备访问

当前 `npm run dev` 主要用于本机访问。

如果需要手机或局域网其他设备访问，可尝试：

```bash
cd frontend
npm run dev -- --host 0.0.0.0
```

然后用本机局域网 IP 访问。

## 10. 本手册关联文件

- `frontend/nuxt.config.ts`
- `frontend/server/api/[...path].ts`
- `backend/app/main.py`
- `backend/app/config.py`
- `docs/README.md`
