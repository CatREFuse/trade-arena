#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT_ROOT="${OPS_PROJECT_ROOT:-$ROOT_DIR}"
LOCK_FILE="${OPS_DEPLOY_LOCK:-/tmp/trade-arena-deploy.lock}"
PENDING_FILE="${OPS_PENDING_FILE:-/tmp/trade-arena-pending-deploy}"
LOG_FILE="${OPS_DEPLOY_LOG:-/var/log/trade-arena-deploy.log}"
NOTIFY_URL="${OPS_NOTIFY_URL:-}"
ALLOWED_BRANCHES="${OPS_ALLOWED_BRANCHES:-main}"
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

send_notify() {
  local info="$1"
  if [[ -z "$NOTIFY_URL" ]]; then
    return
  fi
  local encoded_info
  encoded_info="$(urlencode "$info")"
  curl --noproxy '*' -m 8 -fsS "${NOTIFY_URL}/${encoded_info}" >/dev/null || true
}

is_branch_allowed() {
  local b="$1"
  local normalized
  normalized="$(printf '%s' "$ALLOWED_BRANCHES" | tr ',' ' ')"
  for allowed in $normalized; do
    if [[ "$allowed" == "$b" ]]; then
      return 0
    fi
  done
  return 1
}

log_line() {
  printf '[%s] %s\n' "$(date)" "$1" | tee -a "$LOG_FILE"
}

if [[ -z "$BRANCH" ]]; then
  log_line "Error: No branch specified"
  exit 1
fi

if ! is_branch_allowed "$BRANCH"; then
  log_line "Branch '$BRANCH' is not in OPS_ALLOWED_BRANCHES='$ALLOWED_BRANCHES', skipping deploy"
  exit 1
fi

if [[ -f "$LOCK_FILE" ]]; then
  log_line "Deployment already in progress, skipping..."
  exit 0
fi

touch "$LOCK_FILE"
log_line "Starting deployment for branch: $BRANCH"

cleanup() {
  local exit_code=$?
  local deploy_result="failed"
  if [[ "$DEPLOY_SUCCESS" == "1" && "$exit_code" -eq 0 ]]; then
    deploy_result="succeeded"
  fi
  local deploy_end_time
  deploy_end_time="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  send_notify "stage=end(${deploy_result}) branch=${BRANCH} current_branch=${CURRENT_BRANCH} commit=${PRE_DEPLOY_COMMIT}->${POST_DEPLOY_COMMIT} start=${DEPLOY_START_TIME} end=${deploy_end_time} exit_code=${exit_code}"
  rm -f "$LOCK_FILE"
  log_line "Deployment finished"
  return "$exit_code"
}
trap cleanup EXIT

cd "$PROJECT_ROOT"

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
PRE_DEPLOY_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")"
log_line "Current branch: $CURRENT_BRANCH, target: $BRANCH"
send_notify "stage=start branch=${BRANCH} current_branch=${CURRENT_BRANCH} current_commit=${PRE_DEPLOY_COMMIT} start=${DEPLOY_START_TIME}"

log_line "Switching to branch: $BRANCH"
git fetch origin
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"
git clean -fd
POST_DEPLOY_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")"

log_line "Installing backend dependencies..."
cd "$PROJECT_ROOT/backend"
pip install -e . >>"$LOG_FILE" 2>&1 || pip install fastapi uvicorn sqlalchemy asyncpg alembic pydantic-settings redis sse-starlette yfinance httpx >>"$LOG_FILE" 2>&1

log_line "Running database migrations..."
source .venv/bin/activate
alembic upgrade head >>"$LOG_FILE" 2>&1

log_line "Installing frontend dependencies..."
cd "$PROJECT_ROOT/frontend"
npm ci >>"$LOG_FILE" 2>&1

log_line "Building frontend production bundle..."
rm -rf .nuxt .output
npm run build >>"$LOG_FILE" 2>&1

log_line "Restarting backend..."
pkill -f "uvicorn app.main:app" || true
sleep 2
cd "$PROJECT_ROOT/backend"
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 >>"$LOG_FILE" 2>&1 &

log_line "Restarting frontend..."
pkill -f "node .output/server/index.mjs" || true
pkill -f "npm run start" || true
pkill -f "nuxt preview" || true
pkill -f "nuxt dev" || true
sleep 2
cd "$PROJECT_ROOT/frontend"
nohup env NODE_ENV=production HOST=0.0.0.0 PORT=3000 npm run start >>"$LOG_FILE" 2>&1 &

log_line "Verifying frontend health..."
for i in {1..20}; do
  if curl --noproxy '*' -fsS "http://127.0.0.1:3000" >/dev/null 2>&1; then
    log_line "Frontend is healthy on port 3000"
    break
  fi
  if [[ "$i" -eq 20 ]]; then
    log_line "Frontend failed health check after startup"
    exit 1
  fi
  sleep 2
done

log_line "Verifying console routes..."
CONSOLE_LOGIN_CODE="$(curl --noproxy '*' -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3000/console/login")"
if [[ "$CONSOLE_LOGIN_CODE" != "200" && "$CONSOLE_LOGIN_CODE" != "302" ]]; then
  log_line "/console/login check failed with status: $CONSOLE_LOGIN_CODE"
  exit 1
fi

ADMIN_AUTH_STATUS_CODE="$(curl --noproxy '*' -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3000/api/admin/auth/status")"
if [[ "$ADMIN_AUTH_STATUS_CODE" != "200" ]]; then
  log_line "/api/admin/auth/status check failed with status: $ADMIN_AUTH_STATUS_CODE"
  exit 1
fi

if pgrep -f "nuxt dev" >/dev/null; then
  log_line "Unexpected nuxt dev process detected after deployment"
  exit 1
fi

log_line "Deployment completed successfully!"
DEPLOY_SUCCESS=1

if [[ -f "$PENDING_FILE" ]]; then
  PENDING_BRANCH="$(cat "$PENDING_FILE")"
  rm -f "$PENDING_FILE"
  log_line "Pending deployment detected for branch: $PENDING_BRANCH, redeploying..."
  nohup /bin/bash "$0" "$PENDING_BRANCH" >>"$LOG_FILE" 2>&1 &
fi
