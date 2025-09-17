import os
import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from shared.enums import MicroServiceName
from shared.errors.core import CoreErrors
from shared.users_sync.db import User
from shared.users_sync.schema import UserCreate, UserUpdate


async def get_users(db: AsyncSession, skip: int, limit: int) -> List[User]:
    stmt = select(User).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_user(db: AsyncSession, account_id: uuid.UUID) -> User | None:
    stmt = select(User).where(User.account_id == account_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_user_by_account_id(db: AsyncSession, account_id: uuid.UUID) -> User | None:
    user = await get_user(db=db, account_id=account_id)
    if user is None:
        raise HTTPException(status_code=404, detail=CoreErrors.ACCOUNT_NOT_FOUND)
    return user

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def create_user_account(user_data: UserCreate, db: AsyncSession) -> User:
    new_user = User(
        account_id=user_data.account_id,
        account_id_hash=user_data.account_id_hash,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        email=str(user_data.email),
        profile_picture=user_data.profile_picture,
        date_of_birth=user_data.date_of_birth,
        gender=user_data.gender,
        country_id=user_data.country_id,
        created_at=user_data.created_at,
        updated_at=user_data.updated_at,
        roles=user_data.roles,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    if os.environ['CURRENT_MICRO_SERVICE_NAME'] == MicroServiceName.CORE_SERVICE:
        from shared.users_sync.ms_specific.core_service import create_user_subscription
        await create_user_subscription(new_user, db)
    elif os.environ['CURRENT_MICRO_SERVICE_NAME'] == MicroServiceName.SUBSCRIPTION_SERVICE:
        from subscription_service.services.subscriptions import create_user_for_subscription_ms
        await create_user_for_subscription_ms(new_user, db)
    return new_user

async def update_user(user: User, update_data: UserUpdate, db: AsyncSession) -> User:
    update_data = update_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return user

async def delete_user(user: User, db: AsyncSession):
    user.is_deleted = True
    await db.commit()
    await db.refresh(user)
