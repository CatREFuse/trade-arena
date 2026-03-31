#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "[service_ctl] ERROR: do not source this script. Use: bash scripts/service_ctl.sh <start|stop|restart|status>" >&2
  return 1 2>/dev/null || exit 1
fi

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${RUNTIME_DIR:-$ROOT_DIR/.runtime}"
PID_DIR="$RUNTIME_DIR/pids"
LOG_DIR="$RUNTIME_DIR/logs"

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"
WEBHOOK_PID_FILE="$PID_DIR/webhook.pid"

BACKEND_LOG_FILE="$LOG_DIR/backend.log"
FRONTEND_LOG_FILE="$LOG_DIR/frontend.log"
WEBHOOK_LOG_FILE="$LOG_DIR/webhook.log"

MODE="${MODE:-prod}"                    # dev | prod
START_DOCKER="${START_DOCKER:-1}"       # 1 | 0
STOP_DOCKER="${STOP_DOCKER:-0}"         # 1 | 0
START_WEBHOOK="${START_WEBHOOK:-0}"     # 1 | 0
PREPARE_BACKEND="${PREPARE_BACKEND:-0}" # 1 | 0
PREPARE_FRONTEND="${PREPARE_FRONTEND:-0}" # 1 | 0
HEALTHCHECK="${HEALTHCHECK:-1}"         # 1 | 0
NO_PROXY_VALUE="${NO_PROXY_VALUE:-*}"

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
WEBHOOK_HOST="${WEBHOOK_HOST:-0.0.0.0}"
WEBHOOK_PORT="${WEBHOOK_PORT:-9000}"

if [[ -z "${BUILD_FRONTEND+x}" ]]; then
  if [[ "$MODE" == "prod" ]]; then
    BUILD_FRONTEND=1
  else
    BUILD_FRONTEND=0
  fi
fi

mkdir -p "$PID_DIR" "$LOG_DIR"

log() {
  printf '[service_ctl] %s\n' "$*"
}

fail() {
  printf '[service_ctl] ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage:
  bash scripts/service_ctl.sh <start|stop|restart|status>

Common env vars:
  MODE=prod|dev                 Default: prod
  START_DOCKER=1|0              Default: 1
  STOP_DOCKER=1|0               Default: 0
  START_WEBHOOK=1|0             Default: 0
  PREPARE_BACKEND=1|0           Default: 0
  PREPARE_FRONTEND=1|0          Default: 0
  BUILD_FRONTEND=1|0            Default: prod=1, dev=0
  HEALTHCHECK=1|0               Default: 1

Ports/hosts:
  BACKEND_HOST/BACKEND_PORT     Default: 0.0.0.0:8000
  FRONTEND_HOST/FRONTEND_PORT   Default: 0.0.0.0:3000
  WEBHOOK_HOST/WEBHOOK_PORT     Default: 0.0.0.0:9000
EOF
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

run_compose() {
  local compose_file="$ROOT_DIR/docker-compose.yml"
  local docker_sock=""

  if command_exists docker && docker compose version >/dev/null 2>&1; then
    docker compose -f "$compose_file" "$@"
    return
  fi

  if command_exists docker-compose; then
    # docker-compose v1 often breaks with context-based http+docker endpoints.
    # For this project we always target the local daemon, so force a local context.
    if [[ -S /var/run/docker.sock ]]; then
      docker_sock="/var/run/docker.sock"
    elif [[ -S /run/docker.sock ]]; then
      docker_sock="/run/docker.sock"
    fi

    if [[ -n "$docker_sock" ]]; then
      log "Using docker-compose v1 with local socket: unix://$docker_sock"
      env DOCKER_CONTEXT= DOCKER_HOST="unix://$docker_sock" DOCKER_TLS_VERIFY= DOCKER_CERT_PATH= \
        docker-compose -f "$compose_file" "$@"
    else
      log "Using docker-compose v1 with cleared Docker context variables"
      env DOCKER_CONTEXT= DOCKER_HOST= DOCKER_TLS_VERIFY= DOCKER_CERT_PATH= \
        docker-compose -f "$compose_file" "$@"
    fi
    return
  fi

  echo "[service_ctl] ERROR: No usable compose command found. Install Docker Compose plugin or docker-compose." >&2
  return 1
}

choose_backend_python() {
  if [[ -x "$ROOT_DIR/backend/.venv/bin/python" ]]; then
    printf '%s\n' "$ROOT_DIR/backend/.venv/bin/python"
    return
  fi
  if command_exists python3; then
    printf 'python3\n'
    return
  fi
  if command_exists python; then
    printf 'python\n'
    return
  fi
  fail "No python interpreter found."
}

read_pid() {
  local file="$1"
  if [[ -f "$file" ]]; then
    cat "$file"
  fi
}

pid_running() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1
}

cleanup_stale_pid() {
  local file="$1"
  local pid
  pid="$(read_pid "$file" || true)"
  if [[ -n "${pid:-}" ]] && ! pid_running "$pid"; then
    rm -f "$file"
  fi
}

stop_pid_file() {
  local name="$1"
  local file="$2"
  local pid
  pid="$(read_pid "$file" || true)"
  if [[ -z "${pid:-}" ]]; then
    log "$name not running (pid file absent)."
    return
  fi
  if ! pid_running "$pid"; then
    rm -f "$file"
    log "$name not running (stale pid=$pid removed)."
    return
  fi

  log "Stopping $name (pid=$pid)..."
  kill "$pid" >/dev/null 2>&1 || true
  for _ in {1..15}; do
    if ! pid_running "$pid"; then
      rm -f "$file"
      log "$name stopped."
      return
    fi
    sleep 1
  done

  log "$name did not exit in time, forcing kill (pid=$pid)."
  kill -9 "$pid" >/dev/null 2>&1 || true
  rm -f "$file"
}

wait_http() {
  local name="$1"
  local url="$2"
  local max_retry="${3:-30}"
  local retry=0
  while (( retry < max_retry )); do
    if curl --noproxy "$NO_PROXY_VALUE" -fsS "$url" >/dev/null 2>&1; then
      log "$name health check passed: $url"
      return 0
    fi
    retry=$((retry + 1))
    sleep 1
  done
  fail "$name health check failed: $url"
}

start_docker_if_needed() {
  local compose_output=""

  if [[ "$START_DOCKER" != "1" ]]; then
    return
  fi
  if ! command_exists docker && ! command_exists docker-compose; then
    fail "START_DOCKER=1 but neither docker nor docker-compose was found."
  fi
  log "Starting infra containers (compose up -d)..."
  if ! compose_output="$(run_compose up -d 2>&1)"; then
    if [[ "$compose_output" == *"Not supported URL scheme http+docker"* ]]; then
      log "Compose failed with docker-python http+docker incompatibility. Continue startup without compose."
      log "Tip: if PostgreSQL/Redis are already running, this is safe. Otherwise set START_DOCKER=0 and start dependencies manually."
      return
    fi
    printf '%s\n' "$compose_output" >&2
    fail "Failed to start infra containers via compose."
  fi
  if [[ -n "$compose_output" ]]; then
    printf '%s\n' "$compose_output"
  fi
}

stop_docker_if_needed() {
  local compose_output=""

  if [[ "$STOP_DOCKER" != "1" ]]; then
    return
  fi
  if ! command_exists docker && ! command_exists docker-compose; then
    log "STOP_DOCKER=1 but neither docker nor docker-compose was found, skipped."
    return
  fi
  log "Stopping infra containers (compose down)..."
  if ! compose_output="$(run_compose down 2>&1)"; then
    if [[ "$compose_output" == *"Not supported URL scheme http+docker"* ]]; then
      log "Compose down failed with docker-python http+docker incompatibility, skipped."
      return
    fi
    printf '%s\n' "$compose_output" >&2
    fail "Failed to stop infra containers via compose."
  fi
  if [[ -n "$compose_output" ]]; then
    printf '%s\n' "$compose_output"
  fi
}

prepare_backend_if_needed() {
  if [[ "$PREPARE_BACKEND" != "1" ]]; then
    return
  fi
  local py
  py="$(choose_backend_python)"
  log "Preparing backend dependencies..."
  (
    cd "$ROOT_DIR/backend"
    if [[ "$py" == "python3" || "$py" == "python" ]]; then
      if [[ ! -d ".venv" ]]; then
        "$py" -m venv .venv
      fi
      py="$ROOT_DIR/backend/.venv/bin/python"
    fi
    "$py" -m pip install -U pip
    "$py" -m pip install -e .
  )
}

prepare_frontend_if_needed() {
  if [[ "$PREPARE_FRONTEND" != "1" ]]; then
    return
  fi
  log "Installing frontend dependencies (npm ci)..."
  (cd "$ROOT_DIR/frontend" && npm ci)
}

start_backend() {
  cleanup_stale_pid "$BACKEND_PID_FILE"
  local pid
  pid="$(read_pid "$BACKEND_PID_FILE" || true)"
  if [[ -n "${pid:-}" ]] && pid_running "$pid"; then
    log "Backend already running (pid=$pid)."
    return
  fi

  local py
  py="$(choose_backend_python)"
  log "Starting backend on ${BACKEND_HOST}:${BACKEND_PORT} (mode=$MODE)..."
  (
    cd "$ROOT_DIR/backend"
    if [[ "$MODE" == "dev" ]]; then
      nohup "$py" -m uvicorn app.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
        >>"$BACKEND_LOG_FILE" 2>&1 &
    else
      nohup "$py" -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
        >>"$BACKEND_LOG_FILE" 2>&1 &
    fi
    echo $! >"$BACKEND_PID_FILE"
  )
}

build_frontend_if_needed() {
  if [[ "$BUILD_FRONTEND" != "1" ]]; then
    return
  fi
  log "Building frontend production bundle..."
  (
    cd "$ROOT_DIR/frontend"
    rm -rf .nuxt .output
    npm run build
  )
}

start_frontend() {
  cleanup_stale_pid "$FRONTEND_PID_FILE"
  local pid
  pid="$(read_pid "$FRONTEND_PID_FILE" || true)"
  if [[ -n "${pid:-}" ]] && pid_running "$pid"; then
    log "Frontend already running (pid=$pid)."
    return
  fi

  log "Starting frontend on ${FRONTEND_HOST}:${FRONTEND_PORT} (mode=$MODE)..."
  (
    cd "$ROOT_DIR/frontend"
    if [[ "$MODE" == "dev" ]]; then
      nohup npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
        >>"$FRONTEND_LOG_FILE" 2>&1 &
    else
      nohup env NODE_ENV=production HOST="$FRONTEND_HOST" PORT="$FRONTEND_PORT" npm run start \
        >>"$FRONTEND_LOG_FILE" 2>&1 &
    fi
    echo $! >"$FRONTEND_PID_FILE"
  )
}

start_webhook() {
  if [[ "$START_WEBHOOK" != "1" ]]; then
    return
  fi
  cleanup_stale_pid "$WEBHOOK_PID_FILE"
  local pid
  pid="$(read_pid "$WEBHOOK_PID_FILE" || true)"
  if [[ -n "${pid:-}" ]] && pid_running "$pid"; then
    log "Webhook already running (pid=$pid)."
    return
  fi

  local py
  py="$(choose_backend_python)"
  log "Starting webhook on ${WEBHOOK_HOST}:${WEBHOOK_PORT}..."
  (
    cd "$ROOT_DIR/webhook"
    nohup env WEBHOOK_PORT="$WEBHOOK_PORT" "$py" -m uvicorn main:app --host "$WEBHOOK_HOST" --port "$WEBHOOK_PORT" \
      >>"$WEBHOOK_LOG_FILE" 2>&1 &
    echo $! >"$WEBHOOK_PID_FILE"
  )
}

stop_all() {
  stop_pid_file "webhook" "$WEBHOOK_PID_FILE"
  stop_pid_file "frontend" "$FRONTEND_PID_FILE"
  stop_pid_file "backend" "$BACKEND_PID_FILE"
  stop_docker_if_needed
}

status_one() {
  local name="$1"
  local pid_file="$2"
  local port="$3"
  cleanup_stale_pid "$pid_file"
  local pid
  pid="$(read_pid "$pid_file" || true)"
  if [[ -n "${pid:-}" ]] && pid_running "$pid"; then
    log "$name: running (pid=$pid, port=$port)"
  else
    log "$name: stopped (port=$port)"
  fi
}

status_all() {
  status_one "backend" "$BACKEND_PID_FILE" "$BACKEND_PORT"
  status_one "frontend" "$FRONTEND_PID_FILE" "$FRONTEND_PORT"
  status_one "webhook" "$WEBHOOK_PID_FILE" "$WEBHOOK_PORT"
}

start_all() {
  start_docker_if_needed
  prepare_backend_if_needed
  prepare_frontend_if_needed
  start_backend
  build_frontend_if_needed
  start_frontend
  start_webhook

  if [[ "$HEALTHCHECK" == "1" ]]; then
    wait_http "backend" "http://127.0.0.1:${BACKEND_PORT}/api/health"
    wait_http "frontend" "http://127.0.0.1:${FRONTEND_PORT}/"
    if [[ "$START_WEBHOOK" == "1" ]]; then
      wait_http "webhook" "http://127.0.0.1:${WEBHOOK_PORT}/health"
    fi
  fi

  log "All requested services are started."
}

ACTION="${1:-}"
case "$ACTION" in
  start)
    start_all
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    start_all
    ;;
  status)
    status_all
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage
    exit 1
    ;;
esac
