from typing import List

import identity_service.schemas.user
from identity_service.services.general import get_all_countries
from identity_service.utils.Error_Handling import ErrorCode
from shared.utils.logger import TsLogger
from fastapi import APIRouter, HTTPException, status

from identity_service.routes.deps import SessionDep

logger = TsLogger(name=__name__)

general_router = APIRouter(
    prefix='/general',
    tags=["General"],
)

# get user profile
@general_router.get("/countries", response_model=List[identity_service.schemas.user.Country], status_code=status.HTTP_200_OK)
async def get_countries(db: SessionDep) -> List[identity_service.schemas.user.Country]:
    """ Get all countries """
    try:
        countries = await get_all_countries(db)
        return [identity_service.schemas.user.Country.model_validate(country) for country in countries]
    except Exception as e:
        logger.error(f"Failed to get countries: {str(e)}")
        raise HTTPException(status_code=500, detail=ErrorCode.FAILED_TO_GET_COUNTRIES)