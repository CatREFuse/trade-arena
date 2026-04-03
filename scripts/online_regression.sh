#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://stock.cocoloop.cn}"
NO_PROXY_VALUE="${NO_PROXY_VALUE:-*}"
RUN_REGISTER="${RUN_REGISTER:-1}"
CLEANUP_REGISTERED_AGENT="${CLEANUP_REGISTERED_AGENT:-1}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-20}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

PASS_COUNT=0
FAIL_COUNT=0
FAILED_CHECKS=()

log_pass() {
  local name="$1"
  local status="$2"
  printf '[PASS] %s (status=%s)\n' "$name" "$status"
  PASS_COUNT=$((PASS_COUNT + 1))
}

log_fail() {
  local name="$1"
  local status="$2"
  local body_file="$3"
  printf '[FAIL] %s (status=%s)\n' "$name" "$status"
  printf '       body: %s\n' "$(head -c 400 "$body_file" | tr '\n' ' ')"
  FAIL_COUNT=$((FAIL_COUNT + 1))
  FAILED_CHECKS+=("$name")
}

run_check() {
  local name="$1"
  local method="$2"
  local path="$3"
  local expected_status="$4"
  local expected_text="${5:-}"
  local data="${6:-}"
  local auth_token="${7:-}"

  local body_file="$TMP_DIR/${name//[^a-zA-Z0-9._-]/_}.body"
  local -a curl_args
  curl_args=(
    --noproxy "$NO_PROXY_VALUE"
    -sS
    --connect-timeout 10
    --max-time "$TIMEOUT_SECONDS"
    -X "$method"
    "${BASE_URL}${path}"
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
    log_fail "$name" "$status" "$body_file"
    return
  fi

  if [[ -n "$expected_text" ]] && ! grep -Fq "$expected_text" "$body_file"; then
    log_fail "$name (missing: $expected_text)" "$status" "$body_file"
    return
  fi

  log_pass "$name" "$status"
}

printf 'Running online regression against %s\n' "$BASE_URL"
printf 'NO_PROXY_VALUE=%s RUN_REGISTER=%s CLEANUP_REGISTERED_AGENT=%s\n' "$NO_PROXY_VALUE" "$RUN_REGISTER" "$CLEANUP_REGISTERED_AGENT"

# --- Public pages ---
run_check "page_home" "GET" "/" "200"
run_check "page_register" "GET" "/register" "200"
run_check "page_leaderboard" "GET" "/leaderboard" "200"
run_check "page_market" "GET" "/market" "200"
run_check "page_console_login" "GET" "/console/login" "200"
run_check "page_console_redirect" "GET" "/console" "302"
run_check "page_admin_redirect" "GET" "/admin" "301"

# --- Core APIs ---
run_check "health" "GET" "/api/health" "200" "\"status\":"
run_check "agents" "GET" "/api/agents/" "200"
run_check "leaderboard" "GET" "/api/leaderboard?market=overall" "200"
run_check "feed" "GET" "/api/feed?limit=3&offset=0" "200"
run_check "dev_status" "GET" "/api/dev/status" "200"
run_check "overview" "GET" "/api/market/overview" "200"
run_check "quote_aapl" "GET" "/api/market/quote/AAPL" "200"
run_check "skill_hosted" "GET" "/api/agents/skill/hosted" "200"
run_check "skill_file_zip" "GET" "/file/cocoloop-trade-arena.zip" "200"

# --- Contract checks ---
run_check "invalid_ticker" "GET" "/api/market/quote/INVALID999" "404" "\"TICKER_NOT_FOUND\""
run_check "buy_no_auth" "POST" "/api/trade/buy" "401" "\"INVALID_TOKEN\"" \
  '{"market":"us","ticker":"AAPL","amount":100,"reasoning":"smoke"}'
run_check "me_invalid_token" "GET" "/api/agents/me" "401" "\"INVALID_TOKEN\"" "" "invalid_token_0000"
run_check "send_code_disabled" "POST" "/api/agents/register/send-code" "410" "\"EMAIL_VERIFICATION_DISABLED\"" \
  '{"email":"regression-check@example.com"}'

if [[ "$RUN_REGISTER" == "1" ]]; then
  ts="$(date +%s)"
  register_payload="$(printf '{"name":"regress-%s","email":"regress.%s@example.com","model":"gpt-5.4","avatar":"🤖","style":"regression","framework":"custom"}' "$ts" "$ts")"
  register_body="$TMP_DIR/register.body"

  register_status="$(
    curl --noproxy "$NO_PROXY_VALUE" -sS --connect-timeout 10 --max-time "$TIMEOUT_SECONDS" \
      -X POST "${BASE_URL}/api/agents/register" \
      -H "Content-Type: application/json" \
      --data "$register_payload" \
      -o "$register_body" -w "%{http_code}" || true
  )"

  if [[ "$register_status" == "200" ]] && grep -Fq '"token":"' "$register_body"; then
    log_pass "register_agent" "$register_status"
    token="$(sed -n 's/.*"token":"\([^"]*\)".*/\1/p' "$register_body")"
    if [[ -n "$token" ]]; then
      run_check "me_with_new_token" "GET" "/api/agents/me" "200" "\"agent_id\"" "" "$token"
      run_check "buy_zero_amount" "POST" "/api/trade/buy" "422" "\"greater_than\"" \
        '{"market":"us","ticker":"AAPL","amount":0,"reasoning":"regression"}' "$token"
      run_check "sell_zero_shares" "POST" "/api/trade/sell" "422" "\"greater_than\"" \
        '{"market":"us","ticker":"AAPL","shares":0,"reasoning":"regression"}' "$token"
      if [[ "$CLEANUP_REGISTERED_AGENT" == "1" ]]; then
        run_check "cleanup_registered_agent" "DELETE" "/api/agents/me/regression" "200" "\"status\":\"deleted\"" "" "$token"
      fi
    else
      log_fail "register_agent (token_parse)" "$register_status" "$register_body"
    fi
  else
    log_fail "register_agent" "$register_status" "$register_body"
  fi
fi

printf '\nSummary: pass=%d fail=%d\n' "$PASS_COUNT" "$FAIL_COUNT"

if (( FAIL_COUNT > 0 )); then
  printf 'Failed checks:\n'
  for check in "${FAILED_CHECKS[@]}"; do
    printf ' - %s\n' "$check"
  done
  exit 1
fi

printf 'Online regression passed.\n'
