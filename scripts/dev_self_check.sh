#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

FRONTEND_BASE="${FRONTEND_BASE:-http://localhost:3000}"
BACKEND_BASE="${BACKEND_BASE:-http://localhost:8000}"
NO_PROXY_VALUE="${NO_PROXY_VALUE:-*}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-12}"
REQUIRE_PORTS="${REQUIRE_PORTS:-1}"
CHECK_DOCKER="${CHECK_DOCKER:-auto}"   # auto | 1 | 0
RUN_HTTP_CHECKS="${RUN_HTTP_CHECKS:-1}" # 1 | 0

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0
FAILED_CHECKS=()

log_pass() {
  local name="$1"
  local detail="${2:-}"
  printf '[PASS] %s' "$name"
  if [[ -n "$detail" ]]; then
    printf ' (%s)' "$detail"
  fi
  printf '\n'
  PASS_COUNT=$((PASS_COUNT + 1))
}

log_warn() {
  local name="$1"
  local detail="${2:-}"
  printf '[WARN] %s' "$name"
  if [[ -n "$detail" ]]; then
    printf ' (%s)' "$detail"
  fi
  printf '\n'
  WARN_COUNT=$((WARN_COUNT + 1))
}

log_fail() {
  local name="$1"
  local detail="${2:-}"
  local body_file="${3:-}"
  printf '[FAIL] %s' "$name"
  if [[ -n "$detail" ]]; then
    printf ' (%s)' "$detail"
  fi
  printf '\n'
  if [[ -n "$body_file" && -f "$body_file" ]]; then
    printf '       body: %s\n' "$(head -c 400 "$body_file" | tr '\n' ' ')"
  fi
  FAIL_COUNT=$((FAIL_COUNT + 1))
  FAILED_CHECKS+=("$name")
}

is_listening() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

check_port() {
  local name="$1"
  local port="$2"
  if is_listening "$port"; then
    log_pass "$name" "port=$port"
  else
    if [[ "$REQUIRE_PORTS" == "1" ]]; then
      log_fail "$name" "port=$port not listening"
    else
      log_warn "$name" "port=$port not listening"
    fi
  fi
}

run_http_check() {
  local name="$1"
  local method="$2"
  local url="$3"
  local expected_status="$4"
  local expected_text="${5:-}"
  local data="${6:-}"
  local auth_token="${7:-}"

  local body_file="$TMP_DIR/${name//[^a-zA-Z0-9._-]/_}.body"
  local -a curl_args
  curl_args=(
    --noproxy "$NO_PROXY_VALUE"
    -sS
    --connect-timeout 8
    --max-time "$TIMEOUT_SECONDS"
    -X "$method"
    "$url"
    -o "$body_file"
    -w "%{http_code}"
  )

  if [[ -n "$data" ]]; then
    curl_args+=(-H "Content-Type: application/json" --data "$data")
  fi

  if [[ -n "$auth_token" ]]; then
    curl_args+=(-H "Authorization: Bearer ${auth_token}")
  fi

  local status
  status="$(curl "${curl_args[@]}" || true)"

  if [[ "$status" != "$expected_status" ]]; then
    log_fail "$name" "status=$status expected=$expected_status" "$body_file"
    return
  fi

  if [[ -n "$expected_text" ]] && ! grep -Fq "$expected_text" "$body_file"; then
    log_fail "$name" "missing=$expected_text" "$body_file"
    return
  fi

  log_pass "$name" "status=$status"
}

check_docker_services() {
  local need_check=0
  if [[ "$CHECK_DOCKER" == "1" ]]; then
    need_check=1
  elif [[ "$CHECK_DOCKER" == "auto" ]]; then
    need_check=1
  fi

  if [[ "$need_check" -eq 0 ]]; then
    return
  fi

  if ! command -v docker >/dev/null 2>&1; then
    log_warn "docker_check" "docker command not found, skipped"
    return
  fi

  local running_services
  running_services="$(
    docker compose -f "$ROOT_DIR/docker-compose.yml" ps --services --status running 2>/dev/null || true
  )"

  if [[ -z "$running_services" ]]; then
    if [[ "$CHECK_DOCKER" == "1" ]]; then
      log_fail "docker_services" "no running services from docker-compose.yml"
    else
      log_warn "docker_services" "no running services from docker-compose.yml"
    fi
    return
  fi

  if grep -qx "postgres" <<<"$running_services"; then
    log_pass "docker_postgres_running"
  else
    [[ "$CHECK_DOCKER" == "1" ]] && log_fail "docker_postgres_running" "postgres not running" || log_warn "docker_postgres_running" "postgres not running"
  fi

  if grep -qx "redis" <<<"$running_services"; then
    log_pass "docker_redis_running"
  else
    [[ "$CHECK_DOCKER" == "1" ]] && log_fail "docker_redis_running" "redis not running" || log_warn "docker_redis_running" "redis not running"
  fi
}

printf 'Running dev self-check\n'
printf 'FRONTEND_BASE=%s BACKEND_BASE=%s\n' "$FRONTEND_BASE" "$BACKEND_BASE"
printf 'NO_PROXY_VALUE=%s REQUIRE_PORTS=%s CHECK_DOCKER=%s RUN_HTTP_CHECKS=%s\n' \
  "$NO_PROXY_VALUE" "$REQUIRE_PORTS" "$CHECK_DOCKER" "$RUN_HTTP_CHECKS"

check_docker_services

# local process / port checks
check_port "frontend_port" "3000"
check_port "backend_port" "8000"

if [[ "$RUN_HTTP_CHECKS" == "1" ]]; then
  # backend direct checks
  run_http_check "backend_health" "GET" "${BACKEND_BASE}/api/health" "200" "\"status\":\"ok\""
  run_http_check "backend_invalid_ticker" "GET" "${BACKEND_BASE}/api/market/quote/INVALID999" "404" "\"TICKER_NOT_FOUND\""

  # frontend page + proxy checks
  run_http_check "frontend_home" "GET" "${FRONTEND_BASE}/" "200"
  run_http_check "frontend_proxy_health" "GET" "${FRONTEND_BASE}/api/health" "200" "\"status\":\"ok\""
  run_http_check "frontend_proxy_leaderboard" "GET" "${FRONTEND_BASE}/api/leaderboard?market=overall" "200"
  run_http_check "frontend_proxy_market_overview" "GET" "${FRONTEND_BASE}/api/market/overview" "200"
  run_http_check "frontend_buy_no_auth" "POST" "${FRONTEND_BASE}/api/trade/buy" "401" "\"INVALID_TOKEN\"" \
    '{"market":"us","ticker":"AAPL","amount":100,"reasoning":"dev-self-check"}'
fi

printf '\nSummary: pass=%d warn=%d fail=%d\n' "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT"

if (( FAIL_COUNT > 0 )); then
  printf 'Failed checks:\n'
  for check in "${FAILED_CHECKS[@]}"; do
    printf ' - %s\n' "$check"
  done
  exit 1
fi

printf 'Dev self-check passed.\n'
