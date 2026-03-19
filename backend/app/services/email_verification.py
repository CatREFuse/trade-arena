from __future__ import annotations

import asyncio
import json
import logging
import secrets
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)

EMAIL_CODE_TTL = 600
EMAIL_CODE_COOLDOWN = 60


def normalize_email(email: str) -> str:
    return email.strip().lower()


def code_cache_key(email: str) -> str:
    return f"agent:register:verify:{normalize_email(email)}"


def cooldown_cache_key(email: str) -> str:
    return f"agent:register:cooldown:{normalize_email(email)}"


async def issue_email_code(redis, email: str) -> str:
    normalized = normalize_email(email)
    code = f"{secrets.randbelow(1_000_000):06d}"
    payload = {
        "email": normalized,
        "code": code,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    await redis.setex(code_cache_key(normalized), EMAIL_CODE_TTL, json.dumps(payload))
    await redis.setex(cooldown_cache_key(normalized), EMAIL_CODE_COOLDOWN, "1")
    return code


async def verify_email_code(redis, email: str, code: str) -> bool:
    normalized = normalize_email(email)
    cached = await redis.get(code_cache_key(normalized))
    if not cached:
        return False

    try:
        raw = cached.decode() if isinstance(cached, bytes) else cached
        payload = json.loads(raw)
    except Exception:
        return False

    if payload.get("code") != code:
        return False

    if hasattr(redis, "delete"):
        await redis.delete(code_cache_key(normalized))
    return True


async def send_email_code(email: str, code: str) -> tuple[str, str | None]:
    if settings.smtp_host and settings.smtp_from_email:
        await asyncio.to_thread(_send_email_sync, email, code)
        return "smtp", None

    logger.warning("SMTP not configured, using development email verification fallback for %s: %s", email, code)
    if settings.email_verification_dev_mode:
        return "dev", code
    raise RuntimeError("SMTP not configured")


def _send_email_sync(email: str, code: str) -> None:
    message = EmailMessage()
    sender = settings.smtp_from_email
    if settings.smtp_from_name:
        message["From"] = f"{settings.smtp_from_name} <{sender}>"
    else:
        message["From"] = sender
    message["To"] = email
    message["Subject"] = "Trade Arena 注册验证码"
    message.set_content(
        "你的 Trade Arena 注册验证码如下：\n\n"
        f"{code}\n\n"
        "验证码 10 分钟内有效。若非本人操作，请忽略此邮件。"
    )

    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            _smtp_login(server)
            server.send_message(message)
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        if settings.smtp_use_tls:
            server.starttls()
        _smtp_login(server)
        server.send_message(message)


def _smtp_login(server: smtplib.SMTP) -> None:
    if settings.smtp_username:
        server.login(settings.smtp_username, settings.smtp_password)
