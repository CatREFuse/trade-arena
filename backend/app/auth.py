from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Account


async def get_current_account(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> Account:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            401,
            detail={"error": "INVALID_TOKEN", "message": "Missing Bearer token"},
        )
    token = authorization[7:]
    result = await db.execute(select(Account).where(Account.api_token == token))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            401,
            detail={"error": "INVALID_TOKEN", "message": "Token 无效或已过期"},
        )
    return account
