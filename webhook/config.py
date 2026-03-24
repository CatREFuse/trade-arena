"""Webhook service configuration."""
import os
from pathlib import Path

# Webhook Secret - 用于验证 GitHub 请求
# 生产环境应通过环境变量设置
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "your-webhook-secret-change-me")

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 服务端口号
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "9000"))

# 部署日志文件
DEPLOY_LOG = Path("/var/log/trade-arena-deploy.log")

# 部署锁文件（防止并发部署）
DEPLOY_LOCK = Path("/tmp/trade-arena-deploy.lock")

# Webhook 触发日志（Markdown 格式）
WEBHOOK_LOG = PROJECT_ROOT / "webhook" / "DEPLOY_LOG.md"
