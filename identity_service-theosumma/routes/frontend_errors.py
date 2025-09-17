from typing import List

from identity_service.services.error import add_error, all_frontend_error
from shared.utils.logger import TsLogger
from identity_service.schemas import auth as user_schema
from identity_service.routes.deps import SessionDep, get_current_user_upgrade

from fastapi import APIRouter, HTTPException, Depends, status


logger = TsLogger(name=__name__)

error_router = APIRouter(
    tags=["FrontEnd Errors"],
    dependencies=[Depends(get_current_user_upgrade)]
)
#
# @error_router.get("/all-errors", response_model=List[user_schema.ErrorResponse],status_code=status.HTTP_200_OK)
# async def get_all_errors(db: SessionDep):
#     try:
#         error_data = await all_frontend_error(db)
#         return error_data
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         await db.rollback()
#         raise HTTPException(status_code=500, detail=f"{str(e)}")

@error_router.post("/add-error", response_model=user_schema.ErrorResponse, status_code=status.HTTP_200_OK)
async def add_frontend_error(db:SessionDep, data: user_schema.ErrorDate ):
    try:
        error_data = await add_error(db,data)
        return error_data
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"{str(e)}")
