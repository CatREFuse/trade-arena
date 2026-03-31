"""Webhook and ops gateway configuration."""
from __future__ import annotations

import os
from pathlib import Path


def _normalized_env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default)).strip()


def _parse_branch_allowlist(raw: str) -> tuple[str, ...]:
    tokens = [item.strip() for item in raw.replace(",", " ").split()]
    cleaned = tuple(item for item in tokens if item)
    return cleaned or ("main",)


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
_load_env_file(PROJECT_ROOT / ".env.ops.local")
_load_env_file(PROJECT_ROOT / ".env.ops")

WEBHOOK_PORT = int(_normalized_env("WEBHOOK_PORT", "9000"))
OPS_ENV = _normalized_env("OPS_ENV", "prod").lower()
OPS_ALLOWED_BRANCHES = _parse_branch_allowlist(_normalized_env("OPS_ALLOWED_BRANCHES", "main"))
OPS_RUNTIME_DIR = Path(_normalized_env("OPS_RUNTIME_DIR", str(PROJECT_ROOT / ".runtime" / "ops")))
OPS_LOG_DIR = Path(_normalized_env("OPS_LOG_DIR", str(OPS_RUNTIME_DIR / "logs")))
OPS_JOBS_DIR = OPS_RUNTIME_DIR / "jobs"
OPS_QUEUE_DIR = OPS_RUNTIME_DIR / "queue"
OPS_LOCKS_DIR = OPS_RUNTIME_DIR / "locks"
OPS_RUNNER_LOCK_FILE = OPS_LOCKS_DIR / "runner.lock"
OPS_RUNNER_HEARTBEAT_TIMEOUT_SECONDS = int(_normalized_env("OPS_RUNNER_HEARTBEAT_TIMEOUT_SECONDS", "900"))

WEBHOOK_SECRET = _normalized_env("WEBHOOK_SECRET")
OPS_API_KEY = _normalized_env("OPS_API_KEY")

ALLOW_INSECURE_LOCAL = OPS_ENV == "local"

DEPLOY_LOG = Path(_normalized_env("OPS_DEPLOY_LOG", "/var/log/trade-arena-deploy.log"))
DEPLOY_LOCK = Path(_normalized_env("OPS_DEPLOY_LOCK", "/tmp/trade-arena-deploy.lock"))
PENDING_DEPLOY = Path(_normalized_env("OPS_PENDING_FILE", "/tmp/trade-arena-pending-deploy"))
WEBHOOK_LOG = PROJECT_ROOT / "webhook" / "DEPLOY_LOG.md"
