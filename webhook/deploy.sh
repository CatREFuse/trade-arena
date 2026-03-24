#!/bin/bash
# Trade Arena Auto Deployment Script

set -e

BRANCH=$1
PROJECT_ROOT="/etc/nginx/website/trade-arena"
LOCK_FILE="/tmp/trade-arena-deploy.lock"
LOG_FILE="/var/log/trade-arena-deploy.log"

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
    rm -f "$LOCK_FILE"
    echo "[$(date)] Deployment finished" | tee -a $LOG_FILE
}
trap cleanup EXIT

cd "$PROJECT_ROOT"

# 1. 获取当前分支
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "[$(date)] Current branch: $CURRENT_BRANCH, target: $BRANCH" | tee -a $LOG_FILE

# 2. 切换到目标分支
echo "[$(date)] Switching to branch: $BRANCH" | tee -a $LOG_FILE
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

# 3. 安装后端依赖
echo "[$(date)] Installing backend dependencies..." | tee -a $LOG_FILE
cd "$PROJECT_ROOT/backend"
pip install -e . >> $LOG_FILE 2>&1 || pip install fastapi uvicorn sqlalchemy asyncpg alembic pydantic-settings redis sse-starlette yfinance httpx >> $LOG_FILE 2>&1

# 4. 安装前端依赖
echo "[$(date)] Installing frontend dependencies..." | tee -a $LOG_FILE
cd "$PROJECT_ROOT/frontend"
npm install >> $LOG_FILE 2>&1

# 5. 重启后端服务
echo "[$(date)] Restarting backend..." | tee -a $LOG_FILE
pkill -f "uvicorn app.main:app" || true
sleep 2
cd "$PROJECT_ROOT/backend"
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 >> $LOG_FILE 2>&1 &

# 6. 重启前端服务
echo "[$(date)] Restarting frontend..." | tee -a $LOG_FILE
pkill -f "nuxt dev" || true
sleep 2
cd "$PROJECT_ROOT/frontend"
nohup npm run dev >> $LOG_FILE 2>&1 &

echo "[$(date)] Deployment completed successfully!" | tee -a $LOG_FILE

# 检查是否有待处理的部署
PENDING_FILE="/tmp/trade-arena-pending-deploy"
if [ -f "$PENDING_FILE" ]; then
    PENDING_BRANCH=$(cat "$PENDING_FILE")
    rm -f "$PENDING_FILE"
    echo "[$(date)] Pending deployment detected for branch: $PENDING_BRANCH, redeploying..." | tee -a $LOG_FILE
    # 重新执行部署（使用 nohup 避免被当前进程终止影响）
    nohup /bin/bash "$0" "$PENDING_BRANCH" >> $LOG_FILE 2>&1 &
fi
