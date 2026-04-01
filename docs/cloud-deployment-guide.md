# Trade Arena 云端部署指南

本文档用于在单台 Linux 云服务器（Ubuntu 22.04/24.04）部署当前仓库版本。

部署拓扑：
- Nginx：80/443 对外入口
- Frontend（Nuxt SSR）：127.0.0.1:3000
- Backend（FastAPI）：127.0.0.1:8000
- PostgreSQL + Redis：Docker Compose

## 1. 服务器准备

```bash
sudo apt update
sudo apt install -y git curl build-essential nginx python3.11 python3.11-venv python3-pip
```

安装 Node.js 20：

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node -v
npm -v
```

安装 Docker：

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

## 2. 拉取代码

```bash
sudo mkdir -p /opt
sudo chown -R $USER:$USER /opt
cd /opt
git clone <你的仓库地址> trade-arena
cd /opt/trade-arena
```

## 3. 启动 PostgreSQL + Redis

项目根目录已有 `docker-compose.yml`：

```bash
cd /opt/trade-arena
docker compose up -d
docker compose ps
```

## 4. 配置后端环境变量

后端读取 `backend/.env`：

```bash
cat > /opt/trade-arena/backend/.env << 'EOF_ENV'
DATABASE_URL=postgresql+asyncpg://arena:arena_dev@localhost:5432/trade_arena
REDIS_URL=redis://localhost:6379/0

# 生产建议：关闭开发验证码回显
EMAIL_VERIFICATION_DEV_MODE=false

# 如需邮箱验证码，请配置 SMTP
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=Trade Arena
SMTP_USE_TLS=true
SMTP_USE_SSL=false
EOF_ENV
```

## 5. 初始化后端

```bash
cd /opt/trade-arena/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
alembic upgrade head
```

健康检查：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
# 新开终端检查
curl -s http://127.0.0.1:8000/health
```

## 6. 构建前端

```bash
cd /opt/trade-arena/frontend
npm ci
npm run build
```

本地预览检查：

```bash
HOST=127.0.0.1 PORT=3000 node .output/server/index.mjs
# 新开终端检查
curl -I http://127.0.0.1:3000
```

## 7. systemd 常驻进程

### 7.1 Backend 服务

```bash
sudo tee /etc/systemd/system/trade-arena-backend.service > /dev/null << 'EOF'
[Unit]
Description=Trade Arena Backend
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/trade-arena/backend
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/trade-arena/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

把 `User=ubuntu` 改成你的实际登录用户。

### 7.2 Frontend 服务

```bash
sudo tee /etc/systemd/system/trade-arena-frontend.service > /dev/null << 'EOF'
[Unit]
Description=Trade Arena Frontend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/trade-arena/frontend
Environment=NODE_ENV=production
Environment=HOST=127.0.0.1
Environment=PORT=3000
ExecStart=/usr/bin/npm run start
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

启动并设置开机自启：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now trade-arena-backend
sudo systemctl enable --now trade-arena-frontend
sudo systemctl status trade-arena-backend --no-pager
sudo systemctl status trade-arena-frontend --no-pager
```

## 8. Nginx 反向代理

```bash
sudo tee /etc/nginx/sites-available/trade-arena.conf > /dev/null << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    # 后台登录鉴权必须走 Nuxt，才能下发管理端 session / 设备指纹 cookie
    location /api/admin/auth/ {
        proxy_pass http://127.0.0.1:3000/api/admin/auth/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SSE 长连接
    location /api/sse/ {
        proxy_pass http://127.0.0.1:8000/api/sse/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/trade-arena.conf /etc/nginx/sites-enabled/trade-arena.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 9. HTTPS（Let's Encrypt）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 10. 发布与更新流程

每次发布：

```bash
cd /opt/trade-arena
git pull

cd /opt/trade-arena/backend
source .venv/bin/activate
pip install -e .
alembic upgrade head
sudo systemctl restart trade-arena-backend

cd /opt/trade-arena/frontend
npm ci
npm run build
sudo systemctl restart trade-arena-frontend

sudo systemctl reload nginx
```

## 11. Nuxt 启动故障特征与修复

如果前端日志里出现下面这种报错：

```text
Package import specifier "#internal/nuxt/paths" is not defined in package .../frontend/package.json imported from .../.nuxt/dist/server/server.mjs
```

说明：

- 你启动的是 `.nuxt/dist/server/server.mjs` 这类 Nuxt 内部产物
- 而不是正式的 Nitro 生产入口 `.output/server/index.mjs`

正确修复步骤：

```bash
cd /opt/trade-arena/frontend
rm -rf .nuxt .output
npm ci
npm run build
HOST=127.0.0.1 PORT=3000 node .output/server/index.mjs
```

如果是 systemd 环境，确认 `trade-arena-frontend.service` 的 `ExecStart` 指向的是：

```bash
/usr/bin/npm run start
```

不要指向：

- `nuxt preview`
- `node .nuxt/dist/server/server.mjs`
- 任何 `.nuxt/dist/*` 下的文件

## 12. 故障排查

查看日志：

```bash
sudo journalctl -u trade-arena-backend -f
sudo journalctl -u trade-arena-frontend -f
docker compose logs -f postgres redis
```

快速检查：

```bash
curl -s http://127.0.0.1:8000/health
curl -sI http://127.0.0.1:3000
curl -sI https://your-domain.com
```

## 12. 当前项目部署注意事项

- 前端 `frontend/server/api/[...path].ts` 当前将 API 代理到 `http://127.0.0.1:8000`，因此默认要求前后端部署在同一台服务器。
- 公网 Nginx 需保留 `/api/admin/auth/` 直达 Nuxt 3000 的例外规则，否则 `/console/login` 无法建立后台 session。
- `/api/agents/skill/hosted` 返回 ZIP 下载文件名（`cocoloop-trade-arena.zip`）。
- 生产环境建议配置 SMTP，并将 `EMAIL_VERIFICATION_DEV_MODE` 设为 `false`。
