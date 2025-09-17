import traceback
from io import BytesIO
from typing import Optional, Annotated
from uuid import UUID

import pandas as pd

from identity_service.schemas.auth import AdminUpdateUser
from identity_service.schemas.user import UsersRead, UserRead
from identity_service.routes.deps import CurrentUserUpgrade
from identity_service.services.auth import admin_user, get_users, get_user, admin_update_profile
from shared.utils.logger import TsLogger
from fastapi import APIRouter, HTTPException, Depends, status, Response, Request, UploadFile, Form, Body, File
from identity_service.routes.deps import SessionDep, CurrentUserUpgrade, get_api_key

logger = TsLogger(name=__name__)

admin_router = APIRouter(
    prefix='/admin',
    tags=["Admin"],
)

@admin_router.get(
    "/all-users",
    response_model=UsersRead,
    status_code=status.HTTP_200_OK,
)
async def get_all_users(
    current_user: CurrentUserUpgrade,
    db: SessionDep,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None
):
    try:
        await admin_user(current_user, db)

        result = await get_users(db, skip, limit, search)
        if not result.users:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no_users_found")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_all_users: {e}")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal_error"
        )


@admin_router.get('/{user_id}', response_model=UserRead, status_code=status.HTTP_200_OK)
async def get_user_by_id(
    user_id: UUID,
    current_user: CurrentUserUpgrade,
    db: SessionDep,
):
    try:
        # Ensure the user is an admin (raises if not)
        await admin_user(current_user, db)
        user = await get_user(db,str(user_id))
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no_user_found")
        return UserRead.model_validate(user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_all_users: {e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="internal_error")

@admin_router.put('/{user_id}', response_model=UserRead, status_code=status.HTTP_200_OK)
async def get_user_by_id(
    user_id: UUID,
    current_user: CurrentUserUpgrade,
    update_data: AdminUpdateUser,
    db: SessionDep,
):
    try:
        # Ensure the user is an admin (raises if not)
        await admin_user(current_user, db)
        user = await get_user(db,str(user_id))
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no_user_found")
        user = await admin_update_profile(user,update_data, db)
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no_user_found")
        return UserRead.model_validate(user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_all_users: {e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="internal_error")
