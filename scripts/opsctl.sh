#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "[opsctl] ERROR: do not source this script. Use: bash scripts/opsctl.sh <command>" >&2
  return 1 2>/dev/null || exit 1
fi

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPS_DIR="$ROOT_DIR/scripts/ops"
NO_PROXY_VALUE="${NO_PROXY_VALUE:-*}"
OPS_DEPLOY_LOG="${OPS_DEPLOY_LOG:-/var/log/trade-arena-deploy.log}"
OPS_RUNTIME_LOG_DIR="${OPS_RUNTIME_LOG_DIR:-$ROOT_DIR/.runtime/logs}"
OPS_DEPLOY_LOCK="${OPS_DEPLOY_LOCK:-/tmp/trade-arena-deploy.lock}"
OPS_PENDING_FILE="${OPS_PENDING_FILE:-/tmp/trade-arena-pending-deploy}"

log() {
  printf '[opsctl] %s\n' "$*"
}

fail() {
  printf '[opsctl] ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage:
  bash scripts/opsctl.sh <command> [args]

Commands:
  deploy --branch <name>
  migrate
  restart --target <all|backend|frontend>
  status
  logs --scope <deploy|backend|frontend|webhook|gateway> [--tail <n>]
  smoke --profile <local|prod> [--base-url <url>]
  doctor
  gen-key
  init-secrets [--output <path>] [--force]
  gateway-reload
  run-next-job
EOF
}

parse_required_value() {
  local key="$1"
  local value="${2:-}"
  if [[ -z "$value" ]]; then
    fail "Missing value for $key"
  fi
  printf '%s\n' "$value"
}

cmd_deploy() {
  local branch=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --branch)
        shift
        branch="$(parse_required_value --branch "${1:-}")"
        ;;
      *)
        fail "Unknown deploy option: $1"
        ;;
    esac
    shift
  done

  if [[ -z "$branch" ]]; then
    fail "deploy requires --branch <name>"
  fi

  exec /bin/bash "$OPS_DIR/deploy.sh" "$branch"
}

cmd_migrate() {
  local py="$ROOT_DIR/backend/.venv/bin/python"
  if [[ ! -x "$py" ]]; then
    fail "Backend virtualenv missing: $py"
  fi
  (
    cd "$ROOT_DIR/backend"
    "$py" -m alembic upgrade head
  )
}

cmd_restart() {
  local target="all"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --target)
        shift
        target="$(parse_required_value --target "${1:-}")"
        ;;
      *)
        fail "Unknown restart option: $1"
        ;;
    esac
    shift
  done

  case "$target" in
    all)
      /bin/bash "$ROOT_DIR/scripts/service_ctl.sh" restart
      ;;
    backend|frontend)
      log "Target '$target' currently triggers a full restart to keep dependency order stable."
      /bin/bash "$ROOT_DIR/scripts/service_ctl.sh" restart
      ;;
    *)
      fail "Unsupported restart target: $target"
      ;;
  esac
}

cmd_status() {
  /bin/bash "$ROOT_DIR/scripts/service_ctl.sh" status
  if [[ -f "$OPS_DEPLOY_LOCK" ]]; then
    log "deploy_lock: active ($OPS_DEPLOY_LOCK)"
  else
    log "deploy_lock: idle"
  fi
  if [[ -f "$OPS_PENDING_FILE" ]]; then
    log "pending_deploy: $(cat "$OPS_PENDING_FILE")"
  else
    log "pending_deploy: none"
  fi
}

cmd_logs() {
  local scope="deploy"
  local tail_n="200"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --scope)
        shift
        scope="$(parse_required_value --scope "${1:-}")"
        ;;
      --tail)
        shift
        tail_n="$(parse_required_value --tail "${1:-}")"
        ;;
      *)
        fail "Unknown logs option: $1"
        ;;
    esac
    shift
  done

  local file=""
  case "$scope" in
    deploy) file="$OPS_DEPLOY_LOG" ;;
    backend) file="$OPS_RUNTIME_LOG_DIR/backend.log" ;;
    frontend) file="$OPS_RUNTIME_LOG_DIR/frontend.log" ;;
    webhook|gateway) file="$OPS_RUNTIME_LOG_DIR/webhook.log" ;;
    *)
      fail "Unsupported log scope: $scope"
      ;;
  esac

  if [[ ! -f "$file" ]]; then
    fail "Log file not found: $file"
  fi
  tail -n "$tail_n" "$file"
}

cmd_smoke() {
  local profile="local"
  local base_url="${BASE_URL:-https://stock.cocoloop.cn}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile)
        shift
        profile="$(parse_required_value --profile "${1:-}")"
        ;;
      --base-url)
        shift
        base_url="$(parse_required_value --base-url "${1:-}")"
        ;;
      *)
        fail "Unknown smoke option: $1"
        ;;
    esac
    shift
  done

  case "$profile" in
    local)
      /bin/bash "$ROOT_DIR/scripts/dev_self_check.sh"
      ;;
    prod)
      BASE_URL="$base_url" NO_PROXY_VALUE="$NO_PROXY_VALUE" /bin/bash "$ROOT_DIR/scripts/online_regression.sh"
      ;;
    *)
      fail "Unsupported smoke profile: $profile"
      ;;
  esac
}

cmd_doctor() {
  log "project_root=$ROOT_DIR"
  log "ops_dir=$OPS_DIR"
  for cmd in bash curl git; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      fail "Missing command: $cmd"
    fi
  done
  if [[ ! -x "$ROOT_DIR/scripts/service_ctl.sh" ]]; then
    fail "Missing service_ctl.sh executable"
  fi
  log "doctor checks passed"
}

generate_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
    return
  fi
  local py=""
  if command -v python3 >/dev/null 2>&1; then
    py="python3"
  elif command -v python >/dev/null 2>&1; then
    py="python"
  else
    fail "Missing openssl/python to generate a secret"
  fi
  "$py" - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
}

cmd_gen_key() {
  generate_secret
}

cmd_init_secrets() {
  local output_file="$ROOT_DIR/.env.ops.local"
  local force_write="0"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --output)
        shift
        output_file="$(parse_required_value --output "${1:-}")"
        ;;
      --force)
        force_write="1"
        ;;
      *)
        fail "Unknown init-secrets option: $1"
        ;;
    esac
    shift
  done

  if [[ -f "$output_file" && "$force_write" != "1" ]]; then
    fail "Secrets file already exists: $output_file (use --force to overwrite)"
  fi

  local webhook_secret
  local ops_api_key
  webhook_secret="$(generate_secret)"
  ops_api_key="$(generate_secret)"

  cat >"$output_file" <<EOF
OPS_ENV=prod
WEBHOOK_SECRET=$webhook_secret
OPS_API_KEY=$ops_api_key
OPS_ALLOWED_BRANCHES=main
EOF
  chmod 600 "$output_file" || true
  log "Secrets written: $output_file"
}

cmd_gateway_reload() {
  fail "gateway-reload is blocked by policy. Use manual restart after queue is empty."
}

cmd_run_next_job() {
  local py=""
  if [[ -x "$ROOT_DIR/backend/.venv/bin/python" ]]; then
    py="$ROOT_DIR/backend/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    py="python3"
  elif command -v python >/dev/null 2>&1; then
    py="python"
  else
    fail "No python interpreter found for job runner"
  fi
  exec "$py" "$ROOT_DIR/webhook/job_runner.py"
}

COMMAND="${1:-}"
if [[ -z "$COMMAND" ]]; then
  usage
  exit 1
fi
shift

case "$COMMAND" in
  deploy) cmd_deploy "$@" ;;
  migrate) cmd_migrate "$@" ;;
  restart) cmd_restart "$@" ;;
  status) cmd_status "$@" ;;
  logs) cmd_logs "$@" ;;
  smoke) cmd_smoke "$@" ;;
  doctor) cmd_doctor "$@" ;;
  gen-key) cmd_gen_key "$@" ;;
  init-secrets) cmd_init_secrets "$@" ;;
  gateway-reload) cmd_gateway_reload "$@" ;;
  run-next-job) cmd_run_next_job "$@" ;;
  help|-h|--help) usage ;;
  *)
    usage
    fail "Unknown command: $COMMAND"
    ;;
esac
