#!/usr/bin/env bash
set -euo pipefail

OPS_API_BASE="${OPS_API_BASE:-http://127.0.0.1:9000}"
OPS_API_KEY="${OPS_API_KEY:-}"

log() {
  printf '[ops_http] %s\n' "$*"
}

fail() {
  printf '[ops_http] ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage:
  bash scripts/ops_http.sh <command> [args]

Commands:
  deploy --branch <name> [--wait]
  restart --target <all|backend|frontend> [--wait]
  migrate [--wait]
  smoke --profile <local|prod> [--base-url <url>] [--wait]
  doctor [--wait]
  status
  logs --scope <deploy|backend|frontend|webhook|gateway|job> [--job-id <id>] [--tail <n>]
  job --id <job_id>
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

json_field() {
  local field="$1"
  local payload="${2:-}"
  python3 - "$field" "$payload" <<'PY'
import json
import sys

field = sys.argv[1]
payload = sys.argv[2]
if payload.strip():
    data = json.loads(payload)
else:
    data = {}
value = data
for part in field.split("."):
    if isinstance(value, dict):
        value = value.get(part)
    else:
        value = None
        break
if value is None:
    print("")
elif isinstance(value, (dict, list)):
    print(json.dumps(value, ensure_ascii=False))
else:
    print(value)
PY
}

call_api() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  local tmp_body
  tmp_body="$(mktemp)"
  local http_code
  local -a args
  args=(-sS -X "$method" "$OPS_API_BASE$path" -H "Content-Type: application/json" -o "$tmp_body" -w "%{http_code}")
  if [[ -n "$OPS_API_KEY" ]]; then
    args+=(-H "Authorization: Bearer $OPS_API_KEY")
  fi
  if [[ -n "$body" ]]; then
    args+=(--data "$body")
  fi

  http_code="$(curl "${args[@]}")"
  if [[ "$http_code" -lt 200 || "$http_code" -gt 299 ]]; then
    cat "$tmp_body" >&2
    rm -f "$tmp_body"
    fail "HTTP ${http_code} for ${method} ${path}"
  fi
  cat "$tmp_body"
  rm -f "$tmp_body"
}

wait_job() {
  local job_id="$1"
  local max_rounds="${2:-120}"
  local round=0

  while (( round < max_rounds )); do
    local resp
    local status_text
    local summary
    resp="$(call_api GET "/ops/jobs/${job_id}")"
    status_text="$(json_field "status" "$resp")"
    summary="$(json_field "summary" "$resp")"
    log "job=${job_id} status=${status_text} summary=${summary}"
    case "$status_text" in
      succeeded)
        printf '%s\n' "$resp"
        return 0
        ;;
      failed|cancelled)
        printf '%s\n' "$resp"
        return 1
        ;;
    esac
    round=$((round + 1))
    sleep 3
  done

  fail "Timed out waiting for job ${job_id}"
}

submit_job_and_optionally_wait() {
  local path="$1"
  local body="$2"
  local should_wait="$3"

  local resp
  local job_id
  resp="$(call_api POST "$path" "$body")"
  job_id="$(json_field "job_id" "$resp")"
  if [[ -z "$job_id" ]]; then
    printf '%s\n' "$resp"
    fail "No job_id returned from $path"
  fi

  log "queued job_id=${job_id}"
  if [[ "$should_wait" == "1" ]]; then
    wait_job "$job_id"
  else
    printf '%s\n' "$resp"
  fi
}

cmd_deploy() {
  local branch=""
  local wait_flag="0"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --branch)
        shift
        branch="$(parse_required_value --branch "${1:-}")"
        ;;
      --wait)
        wait_flag="1"
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
  submit_job_and_optionally_wait "/ops/jobs/deploy" "{\"branch\":\"$branch\",\"source\":\"human\"}" "$wait_flag"
}

cmd_restart() {
  local target="all"
  local wait_flag="0"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --target)
        shift
        target="$(parse_required_value --target "${1:-}")"
        ;;
      --wait)
        wait_flag="1"
        ;;
      *)
        fail "Unknown restart option: $1"
        ;;
    esac
    shift
  done
  submit_job_and_optionally_wait "/ops/jobs/service" "{\"action\":\"restart\",\"target\":\"$target\"}" "$wait_flag"
}

cmd_migrate() {
  local wait_flag="0"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --wait)
        wait_flag="1"
        ;;
      *)
        fail "Unknown migrate option: $1"
        ;;
    esac
    shift
  done
  submit_job_and_optionally_wait "/ops/jobs/migrate" "{\"revision\":\"head\",\"source\":\"human\"}" "$wait_flag"
}

cmd_smoke() {
  local profile="local"
  local base_url=""
  local wait_flag="0"
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
      --wait)
        wait_flag="1"
        ;;
      *)
        fail "Unknown smoke option: $1"
        ;;
    esac
    shift
  done
  if [[ -n "$base_url" ]]; then
    submit_job_and_optionally_wait "/ops/jobs/smoke" "{\"profile\":\"$profile\",\"base_url\":\"$base_url\",\"source\":\"human\"}" "$wait_flag"
  else
    submit_job_and_optionally_wait "/ops/jobs/smoke" "{\"profile\":\"$profile\",\"source\":\"human\"}" "$wait_flag"
  fi
}

cmd_doctor() {
  local wait_flag="0"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --wait)
        wait_flag="1"
        ;;
      *)
        fail "Unknown doctor option: $1"
        ;;
    esac
    shift
  done
  submit_job_and_optionally_wait "/ops/jobs/doctor" "{\"source\":\"human\"}" "$wait_flag"
}

cmd_status() {
  call_api GET "/ops/status"
}

cmd_logs() {
  local scope="deploy"
  local tail_n="200"
  local job_id=""
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
      --job-id)
        shift
        job_id="$(parse_required_value --job-id "${1:-}")"
        ;;
      *)
        fail "Unknown logs option: $1"
        ;;
    esac
    shift
  done
  if [[ "$scope" == "job" ]]; then
    if [[ -z "$job_id" ]]; then
      fail "logs --scope job requires --job-id <id>"
    fi
    call_api GET "/ops/logs?scope=job&job_id=${job_id}&tail=${tail_n}"
    return
  fi
  call_api GET "/ops/logs?scope=${scope}&tail=${tail_n}"
}

cmd_job() {
  local job_id=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --id)
        shift
        job_id="$(parse_required_value --id "${1:-}")"
        ;;
      *)
        fail "Unknown job option: $1"
        ;;
    esac
    shift
  done
  if [[ -z "$job_id" ]]; then
    fail "job requires --id <job_id>"
  fi
  call_api GET "/ops/jobs/${job_id}"
}

COMMAND="${1:-}"
if [[ -z "$COMMAND" ]]; then
  usage
  exit 1
fi
shift

case "$COMMAND" in
  deploy) cmd_deploy "$@" ;;
  restart) cmd_restart "$@" ;;
  migrate) cmd_migrate "$@" ;;
  smoke) cmd_smoke "$@" ;;
  doctor) cmd_doctor "$@" ;;
  status) cmd_status "$@" ;;
  logs) cmd_logs "$@" ;;
  job) cmd_job "$@" ;;
  help|-h|--help) usage ;;
  *)
    usage
    fail "Unknown command: $COMMAND"
    ;;
esac
