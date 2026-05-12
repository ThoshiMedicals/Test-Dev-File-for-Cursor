from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import require_api_key

DbDep = Depends(get_db)
AuthDep = Depends(require_api_key)


async def db_dep(db: AsyncSession = DbDep) -> AsyncSession:  # pragma: no cover
    return db


async def auth_dep(_: None = AuthDep) -> None:  # pragma: no cover
    return None

