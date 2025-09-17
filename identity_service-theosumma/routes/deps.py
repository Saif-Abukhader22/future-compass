import logging
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession


from starlette import status

from identity_service.DB import get_db
from identity_service.config import settings
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import jwt, JWTError, ExpiredSignatureError
from starlette.status import HTTP_403_FORBIDDEN

from identity_service.utils import security
from shared.config import shared_settings
from shared.errors.identity import IdentityErrors
from shared.ts_ms.ms_manager import MsManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# reusable_oauth2 = OAuth2PasswordBearer(
#     # tokenUrl="https://ts-core-api.theosumma.com/auth/api/Authentication/Login"
#     tokenUrl=f"{settings.API_V1_STR}/login/access-token"
# )

reusable_oauth2 = OAuth2PasswordBearer(
    # tokenUrl="https://ts-core-api.theosumma.com/auth/api/Authentication/Login"
    tokenUrl=MsManager.get_login_url()

)

SessionDep = Annotated[AsyncSession, Depends(get_db)]

# Define the API key header scheme
header_scheme = APIKeyHeader(name=shared_settings.API_KEY_NAME)

TokenDep = Annotated[str, Depends(reusable_oauth2)]

#
async def get_api_key(api_key: str = Depends(header_scheme)):
    if api_key == shared_settings.API_KEY:
        return api_key
    else:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Could not validate API key"
        )

#The old signature
# async def get_current_user(db: SessionDep, token: TokenDep):

async def get_current_user(token: TokenDep):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode the JWT with signature verification, and add audience and issuer claims for additional security
        payload = jwt.decode(
            token,
            shared_settings.JWT_AT_SECRET,
            algorithms=[security.ALGORITHM]
            # options={
            #     'verify_aud': False, # Disable audience verification
            #     'verify_iss': False, # Disable issuer verification
            # }
            # audience="your_audience_here",  # Update with the actual audience expected
            # issuer="https://ts-core-api.theosumma.com"  # Set to your ASP.NET Core server's URL
        )

        # Extract the user ID and verify it
        user_id = payload.get("user_id")
        if not user_id:
            raise credentials_exception

        return user_id

        # Validate the token payload format
        # token_data = TokenPayload(**payload)

    except (JWTError, ValidationError) as e:
        logger.error(f"JWT validation error: {str(e)}")
        raise credentials_exception from e  # Raise with additional context

    # Fetch the user from the database and handle the case where the user is not found
    # user = await db.execute(
    #     select(User)
    #     .filter(user_id == User.user_id)
    # )
    # if not user:
    #     logger.warning(f"User not found: {token_data.sub}")
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")



async def get_current_user_upgrade(token: TokenDep) -> UUID:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=IdentityErrors.INVALID_CREDENTIALS,
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            shared_settings.JWT_AT_SECRET,
            algorithms=[security.ALGORITHM]
        )
        user_id = payload.get("user_id")
        if not user_id:
            raise credentials_exception

        return UUID(user_id)

    except ExpiredSignatureError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=IdentityErrors.ACCESS_TOKEN_EXPIRED)
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=IdentityErrors.INVALID_ACCESS_TOKEN)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Error decoding token: {str(e)}")

CurrentUser = Annotated[str, Depends(get_current_user)]
CurrentUserUpgrade = Annotated[UUID, Depends(get_current_user_upgrade)]

