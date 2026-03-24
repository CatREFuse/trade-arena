"""GitHub Webhook receiver for CI/CD."""
from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from config import DEPLOY_LOCK, DEPLOY_LOG, PENDING_DEPLOY, PROJECT_ROOT, WEBHOOK_LOG, WEBHOOK_PORT, WEBHOOK_SECRET

app = FastAPI(title="Trade Arena Webhook", version="1.0.0")


def verify_signature(body: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature."""
    if not signature.startswith("sha256="):
        return False
    
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def log_pending_event(branch: str, repository: str, pusher: dict, commit_msg: str = "") -> None:
    """Log pending deployment event to markdown file."""
    from datetime import datetime
    
    if not WEBHOOK_LOG.exists():
        WEBHOOK_LOG.write_text("# Webhook Deployment Log\n\n", encoding="utf-8")
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pusher_name = pusher.get("name", "unknown") if pusher else "unknown"
    pusher_email = pusher.get("email", "") if pusher else ""
    
    log_entry = f"""## {timestamp}

- **Branch**: `{branch}`
- **Repository**: {repository}
- **Pusher**: {pusher_name} ({pusher_email})
- **Status**: ⏳ Queued (waiting for current deployment)
- **Commit Message**: {commit_msg or "N/A"}

---

"""
    
    content = WEBHOOK_LOG.read_text(encoding="utf-8")
    content = content.replace(
        "# Webhook Deployment Log\n\n",
        f"# Webhook Deployment Log\n\n{log_entry}"
    )
    WEBHOOK_LOG.write_text(content, encoding="utf-8")


def log_webhook_event(branch: str, repository: str, pusher: dict, commit_msg: str = "") -> None:
    """Log webhook trigger event to markdown file."""
    from datetime import datetime
    
    # 初始化日志文件（如果不存在）
    if not WEBHOOK_LOG.exists():
        WEBHOOK_LOG.write_text("# Webhook Deployment Log\n\n", encoding="utf-8")
    
    # 构建日志条目
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pusher_name = pusher.get("name", "unknown") if pusher else "unknown"
    pusher_email = pusher.get("email", "") if pusher else ""
    
    log_entry = f"""## {timestamp}

- **Branch**: `{branch}`
- **Repository**: {repository}
- **Pusher**: {pusher_name} ({pusher_email})
- **Status**: ✅ Deployment triggered
- **Commit Message**: {commit_msg or "N/A"}

---

"""
    
    # 追加到日志文件（插入到标题后面）
    content = WEBHOOK_LOG.read_text(encoding="utf-8")
    # 在标题后插入新记录
    content = content.replace(
        "# Webhook Deployment Log\n\n",
        f"# Webhook Deployment Log\n\n{log_entry}"
    )
    WEBHOOK_LOG.write_text(content, encoding="utf-8")


def run_deploy(branch: str) -> None:
    """Run deployment script asynchronously."""
    deploy_script = Path(__file__).parent / "deploy.sh"
    
    # 使用 nohup 让脚本在后台运行
    subprocess.Popen(
        ["/bin/bash", str(deploy_script), branch],
        stdout=open(DEPLOY_LOG, "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
        cwd=PROJECT_ROOT
    )


@app.post("/webhook")
async def webhook(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
):
    """Receive GitHub webhook push events."""
    # 读取请求体
    body = await request.body()
    
    # 验证签名
    if not verify_signature(body, x_hub_signature_256):
        raise HTTPException(401, detail="Invalid signature")
    
    # 只处理 push 事件
    if x_github_event != "push":
        return JSONResponse({"message": "Event ignored", "event": x_github_event})
    
    # 解析 payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, detail="Invalid JSON payload")
    
    # 获取分支名（refs/heads/main → main）
    ref = payload.get("ref", "")
    if not ref.startswith("refs/heads/"):
        return JSONResponse({"message": "Not a branch push", "ref": ref})
    
    branch = ref.replace("refs/heads/", "")
    repository = payload.get("repository", {}).get("full_name", "unknown")
    pusher = payload.get("pusher", {})
    
    # 获取最新 commit message
    commits = payload.get("commits", [])
    commit_msg = commits[0].get("message", "") if commits else ""
    
    # 检查部署锁
    if DEPLOY_LOCK.exists():
        # 标记有待处理的部署
        PENDING_DEPLOY.write_text(branch, encoding="utf-8")
        
        # 记录到日志
        log_pending_event(branch, repository, pusher, commit_msg)
        
        return JSONResponse({
            "message": "Deployment queued (another deployment in progress)",
            "branch": branch,
            "status": "queued"
        })
    
    # 记录到 markdown 日志
    log_webhook_event(branch, repository, pusher, commit_msg)
    
    # 触发部署
    run_deploy(branch)
    
    return JSONResponse({
        "message": "Deployment triggered",
        "branch": branch,
        "repository": repository,
        "commit_message": commit_msg
    })


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "webhook"}


@app.get("/webhook/logs")
async def get_webhook_logs():
    """Get webhook deployment logs."""
    if not WEBHOOK_LOG.exists():
        return {"logs": "No logs yet"}
    
    content = WEBHOOK_LOG.read_text(encoding="utf-8")
    return {"logs": content}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=WEBHOOK_PORT)
