import os
import traceback
import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Depends

from shared.enums import MicroServiceName
from shared.errors.core import CoreErrors
from shared.errors.identity import IdentityErrors
from shared.schemas.core.user import UserSubscriptionRead, UserSubscriptionUpdate
from shared.users_sync import SessionDep, get_api_key
from shared.users_sync.schema import UserRead, UserCreate, UserUpdate
from shared.users_sync.service import get_users, get_user, update_user, delete_user, create_user_account

user_sync_router = APIRouter(
    prefix="/accounts",
    tags=["Syncing Accounts"],
    dependencies=[Depends(get_api_key)]  # Apply the global APIKeyDep dependency
)


@user_sync_router.get("/", response_model=List[UserRead])
async def read_users(db: SessionDep, skip: int = 0, limit: int = 10):
    try:
        users = await get_users(db, skip, limit)
        return [UserRead.model_validate(user) for user in users]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while fetching users: {str(e)}")


@user_sync_router.post("/", response_model=UserRead)
async def create_user(user: UserCreate, db: SessionDep) -> UserRead:
    new_user = await create_user_account(user, db)
    return UserRead.model_validate(new_user)


@user_sync_router.get("/{user_id}", response_model=UserRead)
async def read_user(user_id: uuid.UUID, db: SessionDep) -> UserRead:
    user = await get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=IdentityErrors.USER_NOT_FOUND)
    return UserRead.model_validate(user)


@user_sync_router.put("/{user_id}", response_model=UserRead)
async def update_user_endpoint(user_id: uuid.UUID, update_data: UserUpdate, db: SessionDep) -> UserRead:
    user = await get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=IdentityErrors.USER_NOT_FOUND)

    updated_user = await update_user(user, update_data, db)
    return UserRead.model_validate(updated_user)

@user_sync_router.delete("/{user_id}", response_model=None)
async def delete_user_endpoint(user_id: uuid.UUID, db: SessionDep):
    user = await get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=IdentityErrors.USER_NOT_FOUND)
    await delete_user(user, db)

if os.environ["CURRENT_MICRO_SERVICE_NAME"] == MicroServiceName.CORE_SERVICE:
    from shared.users_sync.ms_specific.core_service import update_user_subscription
    @user_sync_router.put("/{user_id}/subscription", response_model=UserSubscriptionRead)
    async def change_user_subscription(
            user_id: uuid.UUID,
            subscription_update: UserSubscriptionUpdate,
            db: SessionDep
    ) -> UserSubscriptionRead:
        try:
            user = await get_user(db, user_id)
            if user is None:
                raise HTTPException(status_code=404, detail=IdentityErrors.USER_NOT_FOUND)

            updated_subscription = await update_user_subscription(user, subscription_update, db)
            if updated_subscription is None:
                raise HTTPException(status_code=404, detail=CoreErrors.NO_SUBSCRIPTION_FOUND)
            return UserSubscriptionRead.model_validate(updated_subscription)
        except HTTPException as e:
            traceback.print_exc()
            raise HTTPException(status_code=404, detail=CoreErrors.NO_SUBSCRIPTION_FOUND)

