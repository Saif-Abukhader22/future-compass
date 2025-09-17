import traceback

import identity_service.schemas.user
import identity_service.services.auth
import identity_service.services.users
from identity_service.schemas.user import Country
from identity_service.services.general import get_country_by_id
from shared import shared_settings
from shared.data_processing.files_utils import FilesUtils
from shared.enums import MongoDBChatMessageType, CloudFlareFileSource, CloudFlareR2Buckets
from shared.errors.core import CoreErrors
from shared.errors.identity import IdentityErrors
from shared.utils.logger import TsLogger
from fastapi import APIRouter, HTTPException, status, UploadFile

from identity_service.schemas import auth as user_schema
from identity_service.services import auth as auth_services
from identity_service.routes.deps import SessionDep, CurrentUserUpgrade
from identity_service.utils.Error_Handling import ErrorCode


logger = TsLogger(name=__name__)

profile_router = APIRouter(
    prefix='/me',
    tags=["Profile"],
)

# get user profile
@profile_router.get("/", response_model=identity_service.schemas.user.UserRead, status_code=status.HTTP_200_OK)
async def get_user_profile(user_id: CurrentUserUpgrade, db: SessionDep) -> identity_service.schemas.user.UserRead:
    """ This route is used to get user's profile (for Loging Users) """
    user = await identity_service.services.auth.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=ErrorCode.USER_NOT_FOUND)
    user_response = identity_service.schemas.user.UserRead.model_validate(user)
    if user.country_id:
        country = await get_country_by_id(db, user.country_id)
        if country:
            user_response.country = Country.model_validate(country)
    return user_response

@profile_router.put("/email", response_model=user_schema.ResponseMessage, status_code=status.HTTP_202_ACCEPTED)
async def update_user_email(update_data: user_schema.EmailUpdateRequest, db: SessionDep,
                            user_id: CurrentUserUpgrade):
    """ This route is used to update user's email (for Loging Users) """

    user = await identity_service.services.auth.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=ErrorCode.USER_NOT_FOUND)
    if user.email != update_data.email:
        raise HTTPException(status_code=400, detail=ErrorCode.EMAIL_ERROR)
    await auth_services.update_email(user, update_data, db)
    update_data_to_email = {
        "email": update_data.email
    }
    await identity_service.services.auth.update_profile(user, update_data_to_email, db)

    return user_schema.ResponseMessage(message="Email Changed successfully")


@profile_router.put("/change-password", status_code=status.HTTP_200_OK)
async def change_password_for_user(user_data: user_schema.NewPassword, db: SessionDep,
                                   user_id: CurrentUserUpgrade):
    """ This Router Used For Changing Password (for Loging Users)"""
    try:
        user = await identity_service.services.auth.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=ErrorCode.USER_NOT_FOUND)
        await auth_services.user_change_password(user, user_data, db)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to change password: {str(e)}")
        raise HTTPException(status_code=500, detail=IdentityErrors.INTERNAL_SERVER_ERROR)

@profile_router.delete("/deactivate", response_model=user_schema.ResponseMessage, status_code=status.HTTP_200_OK)
async def update_user_status(db: SessionDep, user_id: CurrentUserUpgrade):
    """ This Router Used For Deactivate the Account (for Loging Users)"""
    # TODO: update the is_active filed not is_deleted. Also, make sure to add filter to all quries to not retrieve is_delete or (not) is_active users
    user = await identity_service.services.auth.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=ErrorCode.USER_NOT_FOUND)
    await identity_service.services.auth.update_status(user, db)
    return user_schema.ResponseMessage(message="The User Deactivated successfully")


@profile_router.put("/edit-profile", response_model=user_schema.ResponseMessage, status_code=status.HTTP_200_OK)
async def update_user_status(db: SessionDep, user_id: CurrentUserUpgrade, update_data: user_schema.UserUpdate):
    """ This Router Used For Update the Account (for Loging Users)"""
    # TODO: update the is_active filed not is_deleted. Also, make sure to add filter to all quries to not retrieve is_delete or (not) is_active users
    user = await identity_service.services.auth.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=ErrorCode.USER_NOT_FOUND)
    await identity_service.services.auth.update_profile(user, update_data, db)
    return user_schema.ResponseMessage(message="The User Updated successfully")

@profile_router.post("/upload_profile_picture", status_code=status.HTTP_200_OK)
async def upload_profile_picture(db: SessionDep, user_id: CurrentUserUpgrade, profile_picture: UploadFile):
    """Uploads a profile picture and returns the URL"""
    try:
        # Ensure the profile picture is present before proceeding
        if not profile_picture:
            raise HTTPException(status_code=400, detail="No profile picture uploaded")

        # Call the helper function to upload the file and get the URL
        profile_picture_url = await identity_service.services.auth.upload_profile_picture_helper(
            db=db, user_id=user_id, profile_picture=profile_picture)

        # Return the URL of the uploaded profile picture
        return {"profile_picture_url": profile_picture_url}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error during profile picture upload: {str(e)}")
