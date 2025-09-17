from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from identity_service.DB import FrontEndError
from identity_service.schemas import auth as user_schema


async def add_error(db: AsyncSession, data: user_schema.ErrorDate):
    new_error = FrontEndError(
        path=data.path,
        exception=data.exception,
        traceback=data.traceback
    )
    db.add(new_error)
    await db.commit()
    await db.refresh(new_error)

    return new_error

async def all_frontend_error(db: AsyncSession):
    all_errors = await db.execute(select(FrontEndError).order_by(FrontEndError.time.desc()))
    return all_errors.scalars().all()
