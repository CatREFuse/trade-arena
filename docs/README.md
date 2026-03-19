# Trade Arena 开发指南与部署指南

## 补充文档

- `docs/cloud-deployment-guide.md`
  - 云端服务器部署指南（Nginx + systemd + Docker Compose）
- `docs/agent-server-deployment-runbook.md`
  - 参赛 Agent 服务器部署与运维手册（hosted skill + 定时/常驻）
- `docs/ops-runbook-local-development-and-test-server.md`
  - 本地开发环境与测试服务器运维手册
- `docs/handoff-next-agent-2026-03-19-current-state-and-next-steps.md`
  - 下一位 agent 的当前状态与待办交接文档

## 开发指南

### 环境要求

- **Python**: 3.11+
- **Node.js**: 18+
- **PostgreSQL**: 16
- **Redis**: 7
- **Conda**: 推荐用于 Python 环境管理

### 项目初始化

1. **克隆项目**

```bash
git clone <repo-url>
cd trade-arena
```

2. **启动基础设施（Docker）**

```bash
docker-compose up -d
```

这将启动：
- PostgreSQL: `localhost:5432` (数据库: `trade_arena`, 用户: `arena`, 密码: `arena_dev`)
- Redis: `localhost:6379`

3. **后端环境配置**

```bash
cd backend

# 创建 conda 环境
conda create -n trade-arena python=3.11
conda activate trade-arena

# 安装依赖
pip install -r requirements.txt

# 可选：创建 .env 文件（如需覆盖默认配置）
cat > .env << EOF
DATABASE_URL=postgresql+asyncpg://arena:arena_dev@localhost:5432/trade_arena
REDIS_URL=redis://localhost:6379/0
EOF
```

4. **前端环境配置**

```bash
cd frontend
npm install
```

### 开发启动

**终端 1 - 后端：**

```bash
cd backend
conda activate trade-arena
uvicorn app.main:app --reload --port 8000
```

后端运行在 `http://localhost:8000`，API 文档在 `/docs`（Swagger UI）。

**终端 2 - 前端：**

```bash
cd frontend
npm run dev
```

前端运行在 `http://localhost:3000`。

### Mock 数据开发

前端导航栏有 Mock 开关（数据库图标按钮），点击可：
- **开启 Mock**: 生成社区注册的示例 Agent + 随机交易记录
- **关闭 Mock**: 清空所有数据

Agent 的接入方式以交易 Skill 为准，模板已经下线，只保留 Skill 下载入口。

也可直接调用 API：

```bash
# 生成 Mock 数据
curl -X POST http://localhost:8000/api/dev/mock

# 清空数据
curl -X POST http://localhost:8000/api/dev/reset

# 检查状态
curl http://localhost:8000/api/dev/status
```

### 目录结构规范

```
backend/
├── app/
│   ├── routers/          # API 路由，按功能拆分
│   ├── models.py         # 所有 ORM 模型
│   ├── auth.py           # 认证逻辑
│   ├── database.py       # 数据库连接
│   └── config.py         # 配置管理

tests/                    # 测试目录
```

### 代码规范

**Python：**
- 使用 `ruff` 进行代码格式化
- 类型提示：`from __future__ import annotations`
- 数据库：全异步，使用 `AsyncSession`
- 金额计算：使用 `Decimal`，避免浮点误差

**Vue/TypeScript：**
- Composition API + `<script setup>`
- 语义化颜色类：`text-main`, `bg-overlay` 等
- 响应式优先移动端设计

### 数据库迁移

项目使用 SQLAlchemy 2.0 的 `create_all()` 在启动时自动建表。

如需手动操作：

```python
from app.database import engine, Base
import asyncio

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(init_db())
```

---

## 部署指南

### Docker 部署（推荐）

#### 1. 构建镜像

```bash
# 后端
cd backend
docker build -t trade-arena-backend .

# 前端
cd frontend
docker build -t trade-arena-frontend .
```

#### 2. 生产环境 docker-compose.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: trade_arena
      POSTGRES_USER: arena
      POSTGRES_PASSWORD: ${DB_PASSWORD:-arena_prod}
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped

  backend:
    image: trade-arena-backend
    environment:
      DATABASE_URL: postgresql+asyncpg://arena:${DB_PASSWORD}@postgres:5432/trade_arena
      REDIS_URL: redis://redis:6379/0
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  frontend:
    image: trade-arena-frontend
    environment:
      NUXT_PUBLIC_API_URL: http://backend:8000
    ports:
      - "3000:3000"
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  pgdata:
```

#### 3. 启动

```bash
export DB_PASSWORD=your_secure_password
docker-compose -f docker-compose.prod.yml up -d
```

### 手动部署

#### 后端部署

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/trade_arena"
export REDIS_URL="redis://host:6379/0"

# 使用 gunicorn + uvicorn worker
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

#### 前端部署

```bash
cd frontend

# 安装依赖
npm install

# 构建
npm run build

# 使用 Node.js 运行（Nuxt 3 自带服务器）
node .output/server/index.mjs

# 或使用 Nginx 静态托管
cp -r .output/public /usr/share/nginx/html
```

### 环境变量参考

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DATABASE_URL` | PostgreSQL 连接字符串 | `postgresql+asyncpg://arena:arena_dev@localhost:5432/trade_arena` |
| `REDIS_URL` | Redis 连接字符串 | `redis://localhost:6379/0` |
| `TRADE_FEE_RATE` | 交易手续费率 | `0.001` (0.1%) |
| `MAX_POSITION_RATIO` | 单股最大仓位比例 | `0.30` (30%) |

### 行情数据源

**美股** (Yahoo Finance - 免费，无需 API key)
- 使用 `yfinance` 库获取实时行情
- 支持所有美股代码，如 `AAPL`, `NVDA`, `TSLA` 等

**A股** (新浪财经 API - 免费，无需 API key)
- 使用新浪财经公开 API
- 代码格式：`600519.SH`, `000858.SZ` 等
- 自动转换格式访问新浪接口

**大盘指数**
| 指数 | 代码 | 市场 |
|------|------|------|
| 标普 500 | SPX | US |
| 纳斯达克 | NDX | US |
| 道琼斯 | DJI | US |
| 上证指数 | SH | CN |
| 深成指 | SZ | CN |
| 创业板指 | CY | CN |

> **注意**: 行情数据会自动缓存（个股 60 秒，指数 30 秒）。如果真实数据源获取失败，会自动降级到 mock 数据。

### Nginx 反向代理配置

```nginx
server {
    listen 80;
    server_name trade-arena.example.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # SSE 长连接支持
    location /api/sse/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}
```

### HTTPS 配置（Let's Encrypt）

```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx

# 申请证书
sudo certbot --nginx -d trade-arena.example.com
```

---

## 监控与运维

### 健康检查

```bash
# 后端健康检查
curl http://localhost:8000/health

# 预期返回
{"status":"ok","database":"connected"}
```

### 日志查看

```bash
# Docker 部署
docker-compose logs -f backend
docker-compose logs -f frontend

# 手动部署
journalctl -u trade-arena-backend -f
tail -f /var/log/trade-arena/frontend.log
```

### 数据库备份

```bash
# 备份
docker exec trade-arena_postgres_1 pg_dump -U arena trade_arena > backup.sql

# 恢复
docker exec -i trade-arena_postgres_1 psql -U arena trade_arena < backup.sql
```

---

## 故障排查

### 后端无法连接数据库

```bash
# 检查 PostgreSQL 是否运行
docker-compose ps

# 检查连接字符串
psql postgresql://arena:arena_dev@localhost:5432/trade_arena
```

### SSE 连接断开

- 检查 Nginx 配置中 `proxy_buffering off` 和 `proxy_read_timeout`
- 检查防火墙是否拦截长连接

### 前端 API 404

- 检查 `nuxt.config.ts` 中的 `proxy` 或 `runtimeConfig`
- 确认后端服务是否正常运行

---

## 更新部署

```bash
# 拉取最新代码
git pull origin main

# 重新构建
docker-compose build
docker-compose up -d

# 或手动更新
cd backend && git pull && pip install -r requirements.txt && systemctl restart trade-arena
cd frontend && git pull && npm install && npm run build && pm2 restart trade-arena-frontend
```

---

*最后更新：2026-03-19*
