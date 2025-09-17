import datetime
from datetime import timedelta, timezone, datetime

from jose import jwt, JWTError, ExpiredSignatureError
from passlib.context import CryptContext
from fastapi import HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from identity_service.DB.models.users import User, RefreshToken
from identity_service.config import settings
from identity_service.enums import DeviceType, TokenType
from identity_service.schemas.auth import NewRefreshToken, RefreshTokenPayload, AccessTokenPayload
from identity_service.utils import security
from shared.config import shared_settings
from shared.emails.email import Email
from shared.errors.identity import IdentityErrors
from shared.users_sync.schema import UserRead

from shared.utils.encryption import EncryptionUtility

encryption_utility = EncryptionUtility()

ACCESS_TOKEN_EXPIRY = settings.ACCESS_TOKEN_EXPIRY
REFRESH_TOKEN_EXPIRY_PC = settings.REFRESH_TOKEN_EXPIRY_PC
REFRESH_TOKEN_EXPIRY_MO = settings.REFRESH_TOKEN_EXPIRY_MO
MAX_LOGIN_ATTEMPTS = settings.MAX_LOGIN_ATTEMPTS
JWT_at_SECRET = shared_settings.JWT_AT_SECRET
JWT_rt_SECRET = settings.JWT_RT_SECRET

password_context = CryptContext(schemes=['bcrypt'])


def generate_pass_hash(password: str) -> str:
    return password_context.hash(password)


def verify_hash_pass(password: str, hash: str) -> bool:
    return password_context.verify(password, hash)


def create_jwt_at_token(data: AccessTokenPayload):
    to_encode = data.model_dump().copy()
    initiate = datetime.now(tz=timezone.utc)
    expire = datetime.now(tz=timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRY)

    to_encode.update({
        "iat": initiate,
        "exp": expire,
        "token_type": TokenType.ACCESS_TOKEN.value
    })

    return jwt.encode(to_encode, JWT_at_SECRET, algorithm=security.ALGORITHM)


def create_jwt_rt_token(data: RefreshTokenPayload, device_type: DeviceType, ex_time: datetime | None = None) -> NewRefreshToken:

    to_encode = data.model_dump().copy()
    current_time = datetime.now(tz=timezone.utc)

    if not ex_time:
        ex_time = (
            current_time + timedelta(days=REFRESH_TOKEN_EXPIRY_MO)
            if device_type == DeviceType.MOBILE
            else current_time + timedelta(days=REFRESH_TOKEN_EXPIRY_PC)
        )

    to_encode.update({
        "iat": current_time,
        "exp": ex_time,
        "token_type": TokenType.REFRESH_TOKEN.value
    })

    return NewRefreshToken(
        jwt=jwt.encode(to_encode, JWT_rt_SECRET, algorithm=security.ALGORITHM),
        exp=ex_time
    )


async def get_refresh_token(request: Request, response: Response, db: AsyncSession) -> str:
    try:
        # Read & validate access token from headers
        auth_header = request.headers.get("Authorization", "").strip()
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=403, detail=IdentityErrors.INVALID_AUTHORIZATION_HEADER)

        access_token = auth_header.replace("Bearer ", "", 1).strip()

        # 1) Check if valid/expired access token
        access_token_expired = False
        try:
            access_token = jwt.decode(access_token, JWT_at_SECRET, algorithms=[security.ALGORITHM])
        except ExpiredSignatureError:
            access_token_expired = True
        except JWTError:
            raise HTTPException(status_code=403, detail=IdentityErrors.INVALID_ACCESS_TOKEN)

        # 2) check if access token is not expired and return 422 as refresh token should be only for expired access token
        if not access_token_expired:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=IdentityErrors.ACCESS_TOKEN_NOT_EXPIRED)

        # Read & validate refresh token from cookies
        refresh_token = request.cookies.get("refresh_token", "").strip()

        if not refresh_token:
            raise HTTPException(status_code=403, detail=IdentityErrors.NO_REFRESH_TOKEN_PROVIDED)

        # 3) check if valid/expired refresh token
        try:
            rt_payload = jwt.decode(refresh_token, JWT_rt_SECRET, algorithms=[security.ALGORITHM])
        except ExpiredSignatureError:
            # TODO: delete the token through cronjob
            raise HTTPException(status_code=403, detail=IdentityErrors.REFRESH_TOKEN_EXPIRED)
        except JWTError:
            raise HTTPException(status_code=403, detail=IdentityErrors.INVALID_REFRESH_TOKEN)


        # 4) collect jwt_id and user_id from refresh token
        jwt_id, user_id = rt_payload.get("jwt_id", None), rt_payload.get("user_id", None)
        if not jwt_id or not user_id:
            # that means the business logic was changed, and the JWT is not encoding jwt_id and user_id
            raise HTTPException(status_code=500, detail=IdentityErrors.UNEXPECTED_ERROR)

        # 4.5) TODO: use redis to check if the refresh token is blacklisted to reduce DB load

        # 5) Query database for the refresh token
        rt_query = await db.execute(select(RefreshToken).where(RefreshToken.jwt_id == jwt_id, RefreshToken.user_id == user_id))
        rt_db = rt_query.scalar_one_or_none()

        delete_all_rt = False
        if not rt_db:
            raise HTTPException(status_code=403, detail=IdentityErrors.INVALID_REFRESH_TOKEN)
        if rt_db.is_blackList:
            raise HTTPException(status_code=403, detail=IdentityErrors.INVALID_REFRESH_TOKEN)
        if encryption_utility.decrypt(rt_db.hash_refresh_token) != refresh_token:
            # TODO: when cached blacklist is implemented, the tokens should be deleted not flagged
            rt_query = await db.execute(select(RefreshToken).where(RefreshToken.user_id == user_id))
            for rt in rt_query.scalars().all():
                rt.is_blackList = True
            ############ Send Email ################
            user_query = await db.execute(select(User).where(User.user_id == user_id))
            user_read = UserRead.model_validate(user_query)
            email_service = Email(user_read)
            email_service.send_security_alert_email()
            ########################################

            await db.commit()
            raise HTTPException(status_code=403, detail=IdentityErrors.INVALID_REFRESH_TOKEN)

        # Generate new tokens
        new_access_token = create_jwt_at_token(
            AccessTokenPayload(user_id=str(user_id))
        )

        new_rt_payload = RefreshTokenPayload(
            user_id=str(rt_db.user_id),
            jwt_id=str(rt_db.jwt_id),
            device_type=rt_db.device_type
        )

        new_refresh_token = create_jwt_rt_token(
            data=new_rt_payload,
            device_type=DeviceType(rt_db.device_type),
            ex_time=rt_db.refresh_token_exp
        )

        # Update refresh token hash in the database
        rt_db.hash_refresh_token = encryption_utility.encrypt(new_refresh_token.jwt)
        await db.commit()

        # Set response headers and cookies
        set_refresh_token_in_cookie(response=response, device_type=DeviceType(rt_db.device_type), refresh_token=new_refresh_token.jwt)

        return new_access_token

    except ExpiredSignatureError:
        raise HTTPException(status_code=403, detail=IdentityErrors.REFRESH_TOKEN_EXPIRED)
    except JWTError as e:
        raise HTTPException(status_code=403, detail=IdentityErrors.INVALID_REFRESH_TOKEN)
    except HTTPException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def revoke_refresh_token(user: User, request: Request, response: Response, db: AsyncSession) -> bool:
    """ Revokes a refresh token (async). """
    refresh_token = request.cookies.get("refresh_token", "").strip()
    if not refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token provided")
    try:
        rt_payload = jwt.decode(refresh_token, JWT_rt_SECRET, algorithms=[security.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid refresh token 1")
    jwt_id, _ = rt_payload.get("jwt_id"), rt_payload.get("user_id")
    # Query database for the refresh token.. user_id check was added to make sure the authenticated user is the user who is authorized to revoke their refresh token
    rt_query = await db.execute(select(RefreshToken).where(RefreshToken.jwt_id == jwt_id, RefreshToken.user_id == user.user_id))
    rt_db = rt_query.scalar_one_or_none()
    if not rt_db or rt_db.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Invalid refresh token 2")
    # Revoke the refresh token by deleting it from the database
    await db.delete(rt_db)
    await db.commit()
    return True

def set_refresh_token_in_cookie(response: Response, refresh_token: str, device_type: DeviceType) -> None:
    current_time = datetime.now(tz=timezone.utc)

    if device_type == DeviceType.MOBILE:
        exp_time = current_time + timedelta(days=settings.REFRESH_TOKEN_EXPIRY_MO)
    else:
        exp_time = current_time + timedelta(days=settings.REFRESH_TOKEN_EXPIRY_PC)

    max_age = int((exp_time - current_time).total_seconds())

    is_dev = shared_settings.ENVIRONMENT == "local" or shared_settings.ENVIRONMENT == "development"
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=max_age,
        secure=not is_dev,  # secure=False for local HTTP dev
        samesite=None if is_dev else "Lax",  # allow some cross-origin, avoid full rejection
        # path="/",
        # domain=settings.DOMAIN,
    )
