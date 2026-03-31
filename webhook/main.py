"""GitHub webhook and ops gateway entrypoint."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import (
    ALLOW_INSECURE_LOCAL,
    DEPLOY_LOCK,
    DEPLOY_LOG,
    OPS_ALLOWED_BRANCHES,
    OPS_API_KEY,
    OPS_ENV,
    OPS_JOBS_DIR,
    OPS_LOG_DIR,
    OPS_QUEUE_DIR,
    PENDING_DEPLOY,
    PROJECT_ROOT,
    WEBHOOK_LOG,
    WEBHOOK_PORT,
    WEBHOOK_SECRET,
)

app = FastAPI(title="Trade Arena Webhook", version="2.0.0")

LOCAL_CLIENTS = {"127.0.0.1", "::1", "localhost"}
REDACT_PATTERNS = [
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"), "Bearer ***"),
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "***@***"),
]


class DeployJobRequest(BaseModel):
    branch: str = Field(default="main")
    ref: str | None = None
    source: str = Field(default="human")
    reason: str | None = None


class ServiceJobRequest(BaseModel):
    action: str = Field(default="restart")
    target: str = Field(default="all")
    source: str = Field(default="human")
    reason: str | None = None


class MigrateJobRequest(BaseModel):
    revision: str = Field(default="head")
    source: str = Field(default="human")
    reason: str | None = None


class SmokeJobRequest(BaseModel):
    profile: str = Field(default="local")
    base_url: str | None = None
    source: str = Field(default="human")
    reason: str | None = None


class DoctorJobRequest(BaseModel):
    source: str = Field(default="human")
    reason: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_runtime_dirs() -> None:
    OPS_JOBS_DIR.mkdir(parents=True, exist_ok=True)
    OPS_LOG_DIR.mkdir(parents=True, exist_ok=True)
    OPS_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    WEBHOOK_LOG.parent.mkdir(parents=True, exist_ok=True)


def _is_local_request(request: Request) -> bool:
    client = request.client
    if client is None:
        return False
    return client.host in LOCAL_CLIENTS


def _require_webhook_secret(request: Request) -> str:
    if WEBHOOK_SECRET:
        return WEBHOOK_SECRET
    if ALLOW_INSECURE_LOCAL and _is_local_request(request):
        return ""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="WEBHOOK_SECRET is not configured",
    )


def _require_ops_auth(request: Request, authorization: str) -> None:
    if OPS_API_KEY:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing ops token")
        token = authorization[7:]
        if not hmac.compare_digest(token, OPS_API_KEY):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ops token")
        return

    if ALLOW_INSECURE_LOCAL and _is_local_request(request):
        return

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="OPS_API_KEY is not configured",
    )


def _branch_allowed(branch: str) -> bool:
    return branch in OPS_ALLOWED_BRANCHES


def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def _job_path(job_id: str) -> Path:
    return OPS_JOBS_DIR / f"{job_id}.json"


def _save_job(job: dict[str, Any]) -> None:
    job["updated_at"] = _utc_now()
    _job_path(job["job_id"]).write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_job(job_id: str) -> dict[str, Any] | None:
    path = _job_path(job_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _remove_queue_entries(job_id: str) -> None:
    for qfile in OPS_QUEUE_DIR.glob("*.queue"):
        if qfile.read_text(encoding="utf-8").strip() == job_id:
            qfile.unlink(missing_ok=True)


def _list_jobs(limit: int = 50) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for file in OPS_JOBS_DIR.glob("*.json"):
        try:
            jobs.append(json.loads(file.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    jobs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return jobs[:limit]


def _cancel_queued_deploy(branch: str) -> None:
    for job in _list_jobs(limit=500):
        if job.get("type") != "deploy":
            continue
        if job.get("status") != "queued":
            continue
        if job.get("payload", {}).get("branch") != branch:
            continue
        job["status"] = "cancelled"
        job["result_reason"] = "superseded"
        job["summary"] = "superseded by a newer queued deploy"
        job["finished_at"] = _utc_now()
        _save_job(job)
        _remove_queue_entries(job["job_id"])


def _queue_job(job: dict[str, Any]) -> None:
    _save_job(job)
    queue_name = f"{int(time.time() * 1000)}_{job['job_id']}.queue"
    (OPS_QUEUE_DIR / queue_name).write_text(job["job_id"], encoding="utf-8")


def _spawn_runner() -> None:
    opsctl = PROJECT_ROOT / "scripts" / "opsctl.sh"
    runner_log = OPS_LOG_DIR / "runner.log"
    with runner_log.open("a", encoding="utf-8") as stream:
        subprocess.Popen(
            ["/bin/bash", str(opsctl), "run-next-job"],
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=PROJECT_ROOT,
        )


def _create_job(
    job_type: str,
    payload: dict[str, Any],
    *,
    source: str,
    reason: str | None,
) -> dict[str, Any]:
    job_id = f"job_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
    now = _utc_now()
    return {
        "job_id": job_id,
        "type": job_type,
        "status": "queued",
        "result_reason": "none",
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "finished_at": None,
        "heartbeat_at": now,
        "source": source,
        "reason": reason or "",
        "summary": "queued",
        "payload": payload,
        "log_file": str(OPS_LOG_DIR / f"{job_id}.log"),
    }


def _enqueue_job(
    job_type: str,
    payload: dict[str, Any],
    *,
    source: str = "human",
    reason: str | None = None,
) -> dict[str, Any]:
    if job_type == "deploy":
        branch = str(payload.get("branch", ""))
        _cancel_queued_deploy(branch)

    job = _create_job(job_type, payload, source=source, reason=reason)
    _queue_job(job)
    _spawn_runner()
    return job


def _write_webhook_log(branch: str, repository: str, pusher: dict, commit_msg: str, queued: bool) -> None:
    if not WEBHOOK_LOG.exists():
        WEBHOOK_LOG.write_text("# Webhook Deployment Log\n\n", encoding="utf-8")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pusher_name = pusher.get("name", "unknown") if pusher else "unknown"
    pusher_email = pusher.get("email", "") if pusher else ""
    status_text = "⏳ Queued (job queued)" if queued else "✅ Deployment job created"

    log_entry = f"""## {timestamp}

- **Branch**: `{branch}`
- **Repository**: {repository}
- **Pusher**: {pusher_name} ({pusher_email})
- **Status**: {status_text}
- **Commit Message**: {commit_msg or "N/A"}

---

"""
    content = WEBHOOK_LOG.read_text(encoding="utf-8")
    content = content.replace("# Webhook Deployment Log\n\n", f"# Webhook Deployment Log\n\n{log_entry}")
    WEBHOOK_LOG.write_text(content, encoding="utf-8")


def _tail_lines(path: Path, tail: int) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(lines[-tail:])


def _redact_text(text: str) -> str:
    redacted = text
    for pattern, replacement in REDACT_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    if WEBHOOK_SECRET:
        redacted = redacted.replace(WEBHOOK_SECRET, "***")
    if OPS_API_KEY:
        redacted = redacted.replace(OPS_API_KEY, "***")
    return redacted


async def _handle_github_push(
    request: Request,
    x_hub_signature_256: str,
    x_github_event: str,
) -> JSONResponse:
    body = await request.body()
    secret = _require_webhook_secret(request)
    if secret and not verify_signature(body, x_hub_signature_256, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    if x_github_event != "push":
        return JSONResponse({"message": "Event ignored", "event": x_github_event})

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload") from exc

    ref = payload.get("ref", "")
    if not ref.startswith("refs/heads/"):
        return JSONResponse({"message": "Not a branch push", "ref": ref})

    branch = ref.replace("refs/heads/", "")
    if not _branch_allowed(branch):
        return JSONResponse(
            {
                "message": "Branch ignored by OPS_ALLOWED_BRANCHES",
                "branch": branch,
                "allowed_branches": list(OPS_ALLOWED_BRANCHES),
            }
        )

    repository = payload.get("repository", {}).get("full_name", "unknown")
    pusher = payload.get("pusher", {})
    commits = payload.get("commits", [])
    commit_msg = commits[0].get("message", "") if commits else ""
    commit_sha = payload.get("after", "")

    job = _enqueue_job(
        "deploy",
        payload={"branch": branch, "ref": commit_sha or f"origin/{branch}"},
        source="github",
        reason=commit_msg,
    )

    if DEPLOY_LOCK.exists():
        PENDING_DEPLOY.write_text(branch, encoding="utf-8")
        _write_webhook_log(branch, repository, pusher, commit_msg, queued=True)
    else:
        _write_webhook_log(branch, repository, pusher, commit_msg, queued=False)

    return JSONResponse(
        {
            "message": "Deployment job queued",
            "branch": branch,
            "repository": repository,
            "job_id": job["job_id"],
            "status": job["status"],
            "environment": OPS_ENV,
        }
    )


@app.post("/webhook")
async def webhook_compat(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
):
    """Compatibility endpoint for legacy GitHub webhook path."""
    return await _handle_github_push(request, x_hub_signature_256, x_github_event)


@app.post("/hooks/github/push")
async def webhook_push(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
):
    """Preferred GitHub push webhook endpoint."""
    return await _handle_github_push(request, x_hub_signature_256, x_github_event)


@app.post("/ops/jobs/deploy")
async def create_deploy_job(
    request: Request,
    payload: DeployJobRequest,
    authorization: str = Header(default=""),
):
    _require_ops_auth(request, authorization)
    branch = payload.branch.strip()
    if not _branch_allowed(branch):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"branch '{branch}' is not allowed",
        )
    job = _enqueue_job(
        "deploy",
        payload={"branch": branch, "ref": payload.ref or f"origin/{branch}"},
        source=payload.source,
        reason=payload.reason,
    )
    return {"job_id": job["job_id"], "status": job["status"], "type": job["type"]}


@app.post("/ops/jobs/service")
async def create_service_job(
    request: Request,
    payload: ServiceJobRequest,
    authorization: str = Header(default=""),
):
    _require_ops_auth(request, authorization)
    if payload.action != "restart":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="only restart action is supported")
    if payload.target not in {"all", "backend", "frontend"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target must be all/backend/frontend")
    job = _enqueue_job(
        "service",
        payload={"action": payload.action, "target": payload.target},
        source=payload.source,
        reason=payload.reason or f"service {payload.action}",
    )
    return {"job_id": job["job_id"], "status": job["status"], "type": job["type"]}


@app.post("/ops/jobs/migrate")
async def create_migrate_job(
    request: Request,
    payload: MigrateJobRequest,
    authorization: str = Header(default=""),
):
    _require_ops_auth(request, authorization)
    job = _enqueue_job(
        "migrate",
        payload={"revision": payload.revision},
        source=payload.source,
        reason=payload.reason,
    )
    return {"job_id": job["job_id"], "status": job["status"], "type": job["type"]}


@app.post("/ops/jobs/smoke")
async def create_smoke_job(
    request: Request,
    payload: SmokeJobRequest,
    authorization: str = Header(default=""),
):
    _require_ops_auth(request, authorization)
    if payload.profile not in {"local", "prod"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="profile must be local or prod")
    job = _enqueue_job(
        "smoke",
        payload={"profile": payload.profile, "base_url": payload.base_url},
        source=payload.source,
        reason=payload.reason,
    )
    return {"job_id": job["job_id"], "status": job["status"], "type": job["type"]}


@app.post("/ops/jobs/doctor")
async def create_doctor_job(
    request: Request,
    payload: DoctorJobRequest,
    authorization: str = Header(default=""),
):
    _require_ops_auth(request, authorization)
    job = _enqueue_job(
        "doctor",
        payload={},
        source=payload.source,
        reason=payload.reason,
    )
    return {"job_id": job["job_id"], "status": job["status"], "type": job["type"]}


@app.get("/ops/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    request: Request,
    authorization: str = Header(default=""),
):
    _require_ops_auth(request, authorization)
    job = _load_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return job


@app.get("/ops/status")
async def get_ops_status(
    request: Request,
    authorization: str = Header(default=""),
):
    _require_ops_auth(request, authorization)
    queue_depth = len(list(OPS_QUEUE_DIR.glob("*.queue")))
    recent_jobs = _list_jobs(limit=10)
    deploy_lock = DEPLOY_LOCK.exists()
    pending_branch = PENDING_DEPLOY.read_text(encoding="utf-8").strip() if PENDING_DEPLOY.exists() else ""

    status_output = ""
    try:
        proc = subprocess.run(
            ["/bin/bash", str(PROJECT_ROOT / "scripts" / "opsctl.sh"), "status"],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=PROJECT_ROOT,
        )
        status_output = (proc.stdout or "") + (proc.stderr or "")
    except Exception as exc:  # pragma: no cover
        status_output = f"status probe failed: {exc}"

    return {
        "env": OPS_ENV,
        "allowed_branches": list(OPS_ALLOWED_BRANCHES),
        "queue_depth": queue_depth,
        "deploy_lock_active": deploy_lock,
        "pending_deploy_branch": pending_branch,
        "recent_jobs": recent_jobs,
        "status_output": _redact_text(status_output),
    }


@app.get("/ops/logs")
async def get_ops_logs(
    request: Request,
    scope: str = Query(default="deploy"),
    job_id: str = Query(default=""),
    tail: int = Query(default=200, ge=1, le=2000),
    authorization: str = Header(default=""),
):
    _require_ops_auth(request, authorization)

    if scope == "deploy":
        path = DEPLOY_LOG
    elif scope == "backend":
        path = PROJECT_ROOT / ".runtime" / "logs" / "backend.log"
    elif scope == "frontend":
        path = PROJECT_ROOT / ".runtime" / "logs" / "frontend.log"
    elif scope in {"webhook", "gateway"}:
        path = PROJECT_ROOT / ".runtime" / "logs" / "webhook.log"
    elif scope == "job":
        if not job_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="job_id is required for scope=job")
        path = OPS_LOG_DIR / f"{job_id}.log"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unsupported scope: {scope}")

    content = _tail_lines(path, tail)
    return {"scope": scope, "job_id": job_id or None, "logs": _redact_text(content)}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "webhook",
        "env": OPS_ENV,
        "allowed_branches": list(OPS_ALLOWED_BRANCHES),
    }


@app.get("/webhook/logs")
async def get_webhook_logs(
    request: Request,
    authorization: str = Header(default=""),
):
    _require_ops_auth(request, authorization)
    if not WEBHOOK_LOG.exists():
        return {"logs": "No logs yet"}
    return {"logs": _redact_text(WEBHOOK_LOG.read_text(encoding="utf-8"))}


@app.on_event("startup")
async def _on_startup() -> None:
    _ensure_runtime_dirs()
    _spawn_runner()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=WEBHOOK_PORT)
