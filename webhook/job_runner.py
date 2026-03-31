"""Phase-2 job runner for ops queue."""
from __future__ import annotations

import fcntl
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import (
    OPS_JOBS_DIR,
    OPS_LOCKS_DIR,
    OPS_LOG_DIR,
    OPS_QUEUE_DIR,
    OPS_RUNNER_HEARTBEAT_TIMEOUT_SECONDS,
    OPS_RUNNER_LOCK_FILE,
    PROJECT_ROOT,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_runtime_dirs() -> None:
    OPS_JOBS_DIR.mkdir(parents=True, exist_ok=True)
    OPS_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    OPS_LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    OPS_LOG_DIR.mkdir(parents=True, exist_ok=True)


def _job_path(job_id: str) -> Path:
    return OPS_JOBS_DIR / f"{job_id}.json"


def _load_job(job_id: str) -> dict[str, Any] | None:
    path = _job_path(job_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_job(job: dict[str, Any]) -> None:
    job["updated_at"] = _utc_now()
    _job_path(job["job_id"]).write_text(
        json.dumps(job, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _mark_job(
    job: dict[str, Any],
    *,
    status: str,
    result_reason: str | None = None,
    summary: str | None = None,
    finished: bool = False,
) -> None:
    job["status"] = status
    if result_reason is not None:
        job["result_reason"] = result_reason
    if summary is not None:
        job["summary"] = summary
    if status == "running" and not job.get("started_at"):
        job["started_at"] = _utc_now()
    if finished:
        job["finished_at"] = _utc_now()
    job["heartbeat_at"] = _utc_now()
    _save_job(job)


def _recover_orphaned_jobs() -> None:
    now = datetime.now(timezone.utc)
    for job_file in OPS_JOBS_DIR.glob("*.json"):
        job = json.loads(job_file.read_text(encoding="utf-8"))
        if job.get("status") != "running":
            continue
        heartbeat_raw = job.get("heartbeat_at")
        if not heartbeat_raw:
            job["status"] = "failed"
            job["result_reason"] = "orphaned"
            job["summary"] = "runner restarted without heartbeat"
            job["finished_at"] = _utc_now()
            _save_job(job)
            continue
        heartbeat = datetime.fromisoformat(heartbeat_raw)
        if (now - heartbeat).total_seconds() > OPS_RUNNER_HEARTBEAT_TIMEOUT_SECONDS:
            job["status"] = "failed"
            job["result_reason"] = "orphaned"
            job["summary"] = "job heartbeat timeout"
            job["finished_at"] = _utc_now()
            _save_job(job)


def _build_command(job: dict[str, Any]) -> list[str]:
    payload = job.get("payload", {})
    opsctl = str(PROJECT_ROOT / "scripts" / "opsctl.sh")
    job_type = job.get("type")
    if job_type == "deploy":
        return ["/bin/bash", opsctl, "deploy", "--branch", str(payload["branch"])]
    if job_type == "service":
        return ["/bin/bash", opsctl, "restart", "--target", str(payload.get("target", "all"))]
    if job_type == "migrate":
        return ["/bin/bash", opsctl, "migrate"]
    if job_type == "smoke":
        cmd = ["/bin/bash", opsctl, "smoke", "--profile", str(payload.get("profile", "local"))]
        base_url = payload.get("base_url")
        if base_url:
            cmd.extend(["--base-url", str(base_url)])
        return cmd
    if job_type == "doctor":
        return ["/bin/bash", opsctl, "doctor"]
    raise ValueError(f"Unsupported job type: {job_type}")


def _run_single_job(job: dict[str, Any]) -> None:
    log_file = Path(job["log_file"])
    log_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = _build_command(job)
    _mark_job(job, status="running", result_reason="none", summary=f"running: {' '.join(cmd)}")

    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(f"[{_utc_now()}] start {' '.join(cmd)}\n")
        process = subprocess.Popen(
            cmd,
            stdout=fh,
            stderr=subprocess.STDOUT,
            cwd=PROJECT_ROOT,
        )
        while process.poll() is None:
            job["heartbeat_at"] = _utc_now()
            _save_job(job)
            time.sleep(5)
        code = process.returncode
        fh.write(f"[{_utc_now()}] exit_code={code}\n")

    if code == 0:
        _mark_job(
            job,
            status="succeeded",
            result_reason="none",
            summary="completed",
            finished=True,
        )
        return

    _mark_job(
        job,
        status="failed",
        result_reason="none",
        summary=f"command exit code {code}",
        finished=True,
    )


def _next_queue_file() -> Path | None:
    queue_files = sorted(OPS_QUEUE_DIR.glob("*.queue"))
    if not queue_files:
        return None
    return queue_files[0]


def _consume_queue() -> int:
    while True:
        qfile = _next_queue_file()
        if qfile is None:
            return 0

        job_id = qfile.read_text(encoding="utf-8").strip()
        qfile.unlink(missing_ok=True)
        if not job_id:
            continue

        job = _load_job(job_id)
        if job is None:
            continue
        if job.get("status") != "queued":
            continue

        try:
            _run_single_job(job)
        except Exception as exc:  # pragma: no cover - defensive fallback
            job["status"] = "failed"
            job["result_reason"] = "none"
            job["summary"] = f"runner exception: {exc}"
            job["finished_at"] = _utc_now()
            _save_job(job)


def main() -> int:
    _ensure_runtime_dirs()
    _recover_orphaned_jobs()

    with OPS_RUNNER_LOCK_FILE.open("a+", encoding="utf-8") as lock_fp:
        try:
            fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        return _consume_queue()


if __name__ == "__main__":
    raise SystemExit(main())
