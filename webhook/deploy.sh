#!/bin/bash
# Trade Arena Auto Deployment Script

set -e

BRANCH=$1
PROJECT_ROOT="/etc/nginx/website/trade-arena"
LOCK_FILE="/tmp/trade-arena-deploy.lock"
LOG_FILE="/var/log/trade-arena-deploy.log"
WEBHOOK_BASE="https://api.day.app/kGX9fqRpLM9SjjVvNtHcJc/Stock运维"
DEPLOY_START_TIME="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
DEPLOY_SUCCESS=0
CURRENT_BRANCH="unknown"
PRE_DEPLOY_COMMIT="unknown"
POST_DEPLOY_COMMIT="unknown"

urlencode() {
    python3 - "$1" <<'PY'
import sys
import urllib.parse
print(urllib.parse.quote(sys.argv[1], safe=""))
PY
}

send_webhook() {
    local info="$1"
    local encoded_info
    encoded_info="$(urlencode "$info")"
    curl --noproxy '*' -m 8 -fsS "${WEBHOOK_BASE}/${encoded_info}" >/dev/null || true
}

# 检查分支参数
if [ -z "$BRANCH" ]; then
    echo "[$(date)] Error: No branch specified" | tee -a $LOG_FILE
    exit 1
fi

# 创建锁文件
if [ -f "$LOCK_FILE" ]; then
    echo "[$(date)] Deployment already in progress, skipping..." | tee -a $LOG_FILE
    exit 0
fi

touch "$LOCK_FILE"
echo "[$(date)] Starting deployment for branch: $BRANCH" | tee -a $LOG_FILE

# 清理函数
cleanup() {
    local exit_code=$?
    local deploy_result="失败"
    if [ "${DEPLOY_SUCCESS}" = "1" ] && [ "${exit_code}" -eq 0 ]; then
        deploy_result="成功"
    fi
    local deploy_end_time
    deploy_end_time="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    send_webhook "阶段=结束(${deploy_result}) 分支=${BRANCH} 当前分支=${CURRENT_BRANCH} 提交=${PRE_DEPLOY_COMMIT}->${POST_DEPLOY_COMMIT} 开始时间=${DEPLOY_START_TIME} 结束时间=${deploy_end_time} 退出码=${exit_code}"
    rm -f "$LOCK_FILE"
    echo "[$(date)] Deployment finished" | tee -a $LOG_FILE
    return "$exit_code"
}
trap cleanup EXIT

cd "$PROJECT_ROOT"

# 1. 获取当前分支
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
PRE_DEPLOY_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "[$(date)] Current branch: $CURRENT_BRANCH, target: $BRANCH" | tee -a $LOG_FILE
send_webhook "阶段=开始 分支=${BRANCH} 当前分支=${CURRENT_BRANCH} 当前提交=${PRE_DEPLOY_COMMIT} 开始时间=${DEPLOY_START_TIME}"

# 2. 切换到目标分支
echo "[$(date)] Switching to branch: $BRANCH" | tee -a $LOG_FILE
git fetch origin
git checkout "$BRANCH"
# 避免服务器上残留改动导致 pull 失败，强制对齐到远端分支
git reset --hard "origin/$BRANCH"
git clean -fd
POST_DEPLOY_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# 3. 安装后端依赖并运行数据库迁移
echo "[$(date)] Installing backend dependencies..." | tee -a $LOG_FILE
cd "$PROJECT_ROOT/backend"
pip install -e . >> $LOG_FILE 2>&1 || pip install fastapi uvicorn sqlalchemy asyncpg alembic pydantic-settings redis sse-starlette yfinance httpx >> $LOG_FILE 2>&1

echo "[$(date)] Running database migrations..." | tee -a $LOG_FILE
source .venv/bin/activate
alembic upgrade head >> $LOG_FILE 2>&1

# 4. 安装前端依赖
echo "[$(date)] Installing frontend dependencies..." | tee -a $LOG_FILE
cd "$PROJECT_ROOT/frontend"
npm ci >> $LOG_FILE 2>&1

# 5. 构建前端生产产物
echo "[$(date)] Building frontend production bundle..." | tee -a $LOG_FILE
rm -rf .nuxt .output
npm run build >> $LOG_FILE 2>&1

# 6. 重启后端服务
echo "[$(date)] Restarting backend..." | tee -a $LOG_FILE
pkill -f "uvicorn app.main:app" || true
sleep 2
cd "$PROJECT_ROOT/backend"
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 >> $LOG_FILE 2>&1 &

# 7. 重启前端服务
echo "[$(date)] Restarting frontend..." | tee -a $LOG_FILE
pkill -f "node .output/server/index.mjs" || true
pkill -f "npm run start" || true
pkill -f "nuxt preview" || true
pkill -f "nuxt dev" || true
sleep 2
cd "$PROJECT_ROOT/frontend"
nohup env NODE_ENV=production HOST=0.0.0.0 PORT=3000 npm run start >> $LOG_FILE 2>&1 &

# 8. 前端健康检查
echo "[$(date)] Verifying frontend health..." | tee -a $LOG_FILE
for i in {1..20}; do
    if curl --noproxy '*' -fsS "http://127.0.0.1:3000" > /dev/null 2>&1; then
        echo "[$(date)] Frontend is healthy on port 3000" | tee -a $LOG_FILE
        break
    fi
    if [ "$i" -eq 20 ]; then
        echo "[$(date)] Frontend failed health check after startup" | tee -a $LOG_FILE
        exit 1
    fi
    sleep 2
done

# 9. 核心路由与鉴权接口校验
echo "[$(date)] Verifying console routes..." | tee -a $LOG_FILE
CONSOLE_LOGIN_CODE=$(curl --noproxy '*' -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3000/console/login")
if [ "$CONSOLE_LOGIN_CODE" != "200" ] && [ "$CONSOLE_LOGIN_CODE" != "302" ]; then
    echo "[$(date)] /console/login check failed with status: $CONSOLE_LOGIN_CODE" | tee -a $LOG_FILE
    exit 1
fi

ADMIN_AUTH_STATUS_CODE=$(curl --noproxy '*' -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3000/api/admin/auth/status")
if [ "$ADMIN_AUTH_STATUS_CODE" != "200" ]; then
    echo "[$(date)] /api/admin/auth/status check failed with status: $ADMIN_AUTH_STATUS_CODE" | tee -a $LOG_FILE
    exit 1
fi

if pgrep -f "nuxt dev" > /dev/null; then
    echo "[$(date)] Unexpected nuxt dev process detected after deployment" | tee -a $LOG_FILE
    exit 1
fi

echo "[$(date)] Deployment completed successfully!" | tee -a $LOG_FILE
DEPLOY_SUCCESS=1

# 检查是否有待处理的部署
PENDING_FILE="/tmp/trade-arena-pending-deploy"
if [ -f "$PENDING_FILE" ]; then
    PENDING_BRANCH=$(cat "$PENDING_FILE")
    rm -f "$PENDING_FILE"
    echo "[$(date)] Pending deployment detected for branch: $PENDING_BRANCH, redeploying..." | tee -a $LOG_FILE
    # 重新执行部署（使用 nohup 避免被当前进程终止影响）
    nohup /bin/bash "$0" "$PENDING_BRANCH" >> $LOG_FILE 2>&1 &
fi
