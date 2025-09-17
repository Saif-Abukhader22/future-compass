import traceback
from typing import List, Annotated
from uuid import UUID

from identity_service.DB.enums import UserRole
from identity_service.schemas.user import ContactUsRead
from identity_service.services.contact_us import get_submission, get_all_submissions, add_contact_submission, \
    reply_message
from identity_service.services.auth import  get_user_by_id
from identity_service.utils.Error_Handling import ErrorCode
from shared.utils.logger import TsLogger
from identity_service.schemas import user as user_schema
from identity_service.routes.deps import SessionDep, CurrentUserUpgrade, get_current_user_upgrade

from fastapi import APIRouter, HTTPException, Depends, status


logger = TsLogger(name=__name__)

contact_router = APIRouter(
    prefix='/contact-us',
    tags=["Contact Us"]
)

@contact_router.post("/submissions", response_model=user_schema.ContactUsRead, status_code=status.HTTP_200_OK)
async def create_submission(user_id: CurrentUserUpgrade ,db:SessionDep, data: user_schema.ContactUsCreate ):
    try:
        user = await get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=ErrorCode.USER_NOT_FOUND.value)
        contact_data = await add_contact_submission(user, db,data)
        return ContactUsRead.model_validate(contact_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"{str(e)}")

@contact_router.post("/reply", status_code=status.HTTP_200_OK)
async def response(user_id: CurrentUserUpgrade, data: user_schema.ContactUsResponse, db: SessionDep):
    try:
        user = await get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=ErrorCode.USER_NOT_FOUND.value)

        if UserRole.ADMIN not in user.roles:
            raise HTTPException(status_code=403, detail=ErrorCode.NOT_ADMIN.value)

        db_submission = await get_submission(sub_id=data.submission_id, db=db)
        if not db_submission:
            raise HTTPException(status_code=404, detail=ErrorCode.INVALID_SUBMISSION_ID.value)

        send_response = await reply_message(submission=db_submission, response_data=data, db=db)
        if not send_response:
            raise HTTPException(status_code=500, detail=ErrorCode.FAILED_TO_SEND_RESPONSE.value)

        return None

    except HTTPException as e:
        traceback.print_exc()
        await db.rollback()
        raise e

    except Exception as e:
        traceback.print_exc()
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@contact_router.get("/submissions",
                    response_model=List[user_schema.ContactUsRead],
                    status_code=status.HTTP_200_OK,
                    dependencies=[Depends(get_current_user_upgrade)])
async def get_submissions(db:SessionDep):
    try:
        contacts_data = await get_all_submissions(db)
        return [ContactUsRead.model_validate(contact) for contact in contacts_data]
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"{str(e)}")

@contact_router.get("/submissions/{submission_id}",
                    response_model=user_schema.ContactUsRead,
                    status_code=status.HTTP_200_OK, dependencies=[Depends(get_current_user_upgrade)])
async def get_submission_by_id(submission_id: UUID, db:SessionDep):
    try:
        contact_data = await get_submission(sub_id=submission_id, db=db)
        return ContactUsRead.model_validate(contact_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"{str(e)}")
