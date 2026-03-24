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

from config import DEPLOY_LOCK, DEPLOY_LOG, PROJECT_ROOT, WEBHOOK_PORT, WEBHOOK_SECRET

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
    
    # 检查部署锁
    if DEPLOY_LOCK.exists():
        return JSONResponse(
            {"message": "Deployment already in progress", "branch": branch},
            status_code=409
        )
    
    # 触发部署
    run_deploy(branch)
    
    return JSONResponse({
        "message": "Deployment triggered",
        "branch": branch,
        "repository": payload.get("repository", {}).get("full_name")
    })


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "webhook"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=WEBHOOK_PORT)
