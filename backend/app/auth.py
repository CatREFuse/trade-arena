from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Account


async def get_current_account(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Account:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            401,
            detail={"error": "INVALID_TOKEN", "message": "Missing Bearer token"},
        )
    token = authorization[7:]
    result = await db.execute(select(Account).where(Account.api_token == token))
    account = result.scalars().first()
    if not account:
        raise HTTPException(
            401,
            detail={"error": "INVALID_TOKEN", "message": "Token 无效或已过期"},
        )
    return account


async def get_accessible_account(
    account_id: str,
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
) -> Account:
    """获取当前 token 所属 agent 可访问的账户。

    同一 agent 的 US / CN / HK 账户共享 token，因此这里按 account_id 定位，
    再校验它是否和当前 token 属于同一个 agent。
    """
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            404,
            detail={"error": "ACCOUNT_NOT_FOUND", "message": "账户不存在"},
        )
    if account.agent_id != current_account.agent_id:
        raise HTTPException(
            403,
            detail={"error": "FORBIDDEN", "message": "无权访问此账户"},
        )
    return account
