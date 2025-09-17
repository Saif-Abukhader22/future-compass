import traceback
import uuid
from enum import Enum
from uuid import UUID
from datetime import timedelta, datetime, timezone
import random

import httpx
import pandas as pd
from pydantic import EmailStr
from sqlalchemy import delete, select,  or_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from user_agents import parse
from fastapi import HTTPException, Response, Request, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Union

import identity_service.schemas
from identity_service.DB import UserAuth
from identity_service.DB.enums import AuthProvider, UserRole
from identity_service.enums import DeviceType
from identity_service.schemas.auth import TokenData, AccessTokenPayload, RefreshTokenPayload
from identity_service.schemas.user import UserRead, UserReadForUpload, SocialLoginRequest, UserRoleUpdate, UsersRead
from identity_service.services.users import create_micro_services_users, update_micro_services_users
from identity_service.utils.oauth_verification import verify_facebook_token, verify_google_token
from identity_service.utils.user_utils import generate_pass_hash, verify_hash_pass, create_jwt_at_token, \
    create_jwt_rt_token, set_refresh_token_in_cookie
from identity_service.DB.models.users import User, RefreshToken, DevWhitelistUser, MicroserviceSync
from identity_service.schemas import auth as user_schema
from identity_service.config import settings
from shared.config import shared_settings
from shared.data_processing.files_utils import FilesUtils
from shared.emails.email import Email
from shared.enums import MongoDBChatMessageType, CloudFlareFileSource, CloudFlareR2Buckets
from shared.ts_ms.ms_manager import MsManager
from shared.users_sync.schema import UserCreate, UserUpdate
from identity_service.utils.Error_Handling import ErrorCode

# from google.oauth2 import id_token as google_id_token
# from google.auth.transport import requests as google_requests
# import aiohttp


ACCESS_TOKEN_EXPIRY = settings.ACCESS_TOKEN_EXPIRY
REFRESH_TOKEN_EXPIRY_PC = settings.REFRESH_TOKEN_EXPIRY_PC
REFRESH_TOKEN_EXPIRY_MO = settings.REFRESH_TOKEN_EXPIRY_MO
LOCKOUT_DURATION_MINS = settings.LOCKOUT_DURATION_MINS
MAX_LOGIN_ATTEMPTS = settings.MAX_LOGIN_ATTEMPTS

from shared.utils.encryption import EncryptionUtility

encryption_utility = EncryptionUtility()

#################Helper Functions##########################

async def create_verification_code_general(user: User, db: AsyncSession) -> bool:
    try:
        random_number = random.randint(100000, 999999)
        user.auth.verification_code = str(random_number)
        user.auth.verification_code_exp = datetime.now(tz=timezone.utc) + timedelta(minutes=15)
        await db.commit()
        await db.refresh(user)
        return True
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"{ErrorCode.UNEXPECTED_ERROR}: {str(e)}")

async def check_verification_code_general(user: User, verification_code: str) -> None:
    if not verification_code:
        raise HTTPException(status_code=400, detail=ErrorCode.INVALID_VERIFICATION_CODE)
    if user.auth.verification_code != verification_code:
        raise HTTPException(status_code=400, detail=ErrorCode.INVALID_VERIFICATION_CODE)
    if user.auth.verification_code_exp < datetime.now(tz=timezone.utc):
        raise HTTPException(status_code=400, detail=ErrorCode.EXPIRED_VERIFICATION_CODE)

async def verify_recaptcha(token: str, remote_ip: Optional[str] = None):
    """Verify reCAPTCHA token with Google's API."""
    if settings.RECAPTCHA_DISABLED:
        return True
    url = "https://www.google.com/recaptcha/api/siteverify"
    data = {
        "secret": settings.RECAPTCHA_SECRET_KEY,
        "response": token,
        "remoteip": remote_ip
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=data)
        result = response.json()

        if not result.get("success", False):
            raise HTTPException(status_code=400, detail=ErrorCode.RECAPTCHA_FAILED)
        return True
####################################################

async def get_public_ip():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.ipify.org")
            return response.text
    except httpx.RequestError as e:
        print(f"Failed to get public IP: {e}")
        return "Unknown"
#################Services Functions##########################

async def login_user(request: Request, response: Response, form_data, db: AsyncSession) -> TokenData:
    try:
        email = form_data.username.strip().lower()
        password = form_data.password

        user = await get_user_by_email(db, email)
        if user is None:
            raise HTTPException(status_code=400, detail=ErrorCode.LOGIN_INVALID_ERROR)

        if user.is_old:
            await create_verification_code_general(user, db)
            user_read = UserRead.model_validate(user)
            email_service = Email(user_read)
            #TODO: i send confirming mail Not reset password as he new User
            email_service.send_registration_email(user.auth.verification_code)
            raise HTTPException(status_code=403, detail=ErrorCode.OLD_USER)

        if user.auth is None:
            raise HTTPException(status_code=400, detail=ErrorCode.LOGIN_INVALID_ERROR)

        # TODO: how are you implementing Google or FB registration and authenticating?
        current_time = datetime.now(tz=timezone.utc)
        if user.auth.auth_provider == AuthProvider.LOCAL:

            lockout_until = user.auth.lockout_until
            if user.auth.lockout_until is not None and user.auth.lockout_until > current_time:
                remaining_minutes = int((user.auth.lockout_until - current_time).total_seconds() // 60)
                await db.commit()
                raise HTTPException(
                    status_code=403,
                    detail=ErrorCode.ACCOUNT_LOCKED.format(minutes=remaining_minutes)
                )

            if user.auth.lockout_until and lockout_until < current_time:
                user.auth.failed_login_attempts = 0
                user.auth.lockout_until = None

            if user.auth.hashed_password is None or not verify_hash_pass(password, user.auth.hashed_password):
                user.auth.failed_login_attempts += 1
                if user.auth.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
                    user.auth.lockout_until = current_time + timedelta(minutes=LOCKOUT_DURATION_MINS)
                    await db.commit()
                    raise HTTPException(
                        status_code=403,
                        detail=ErrorCode.ACCOUNT_LOCKED_MINUTES.format(minutes=LOCKOUT_DURATION_MINS)
                    )
                await db.commit()
                raise HTTPException(status_code=400, detail=ErrorCode.LOGIN_INVALID_password_ERROR.value)

        if not user.auth.email_confirmed:
            await create_verification_code_general(user, db)
            ############ Send Email ################
            user_read = UserRead.model_validate(user)
            email_service = Email(user_read)
            email_service.send_registration_email(user.auth.verification_code)
            ########################################

            raise HTTPException(status_code=403, detail=ErrorCode.EMAIL_NOT_CONFIRM.value)

        user.auth.failed_login_attempts = 0
        user.auth.lockout_until = None
        user.last_login = current_time

        user_agent_string = request.headers.get("User-Agent", "Unknown")
        user_agent = parse(user_agent_string)
        device_type = DeviceType.MOBILE if user_agent.is_mobile else DeviceType.PC if user_agent.is_pc else DeviceType.UNKNOWN

        public_ip = await get_public_ip() or request.client.host

        jwt_id = uuid.uuid4()
        at_payload = AccessTokenPayload(user_id=str(user.user_id))
        rt_payload = RefreshTokenPayload(
            user_id=str(user.user_id),
            jwt_id=str(jwt_id),
            device_type=device_type.value
        )

        access_token = create_jwt_at_token(at_payload)
        new_refresh_token = create_jwt_rt_token(data=rt_payload, device_type=device_type)

        encrypted_refresh_token = encryption_utility.encrypt(new_refresh_token.jwt)

        await db.execute(delete(RefreshToken).where(
            RefreshToken.user_id == user.user_id,
            RefreshToken.device_type == device_type.value
        ))

        new_refresh_token_db = RefreshToken(
            jwt_id=jwt_id,
            user_id=user.user_id,
            hash_refresh_token=encrypted_refresh_token,
            public_ip=public_ip,
            device_type=device_type.value,
            refresh_token_exp=new_refresh_token.exp,
        )
        db.add(new_refresh_token_db)
        await db.commit()

        set_refresh_token_in_cookie(response=response, device_type=DeviceType(new_refresh_token_db.device_type), refresh_token=new_refresh_token.jwt)

        return TokenData(access_token=access_token)

    except HTTPException as e:
        await db.rollback()
        if shared_settings.ENVIRONMENT == 'local':
            traceback.print_exc()
        raise e
    except Exception as e:
        await db.rollback()
        if shared_settings.ENVIRONMENT == 'local':
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"{ErrorCode.UNEXPECTED_ERROR}: {str(e)}")
        else:
            raise HTTPException(status_code=500, detail=ErrorCode.UNEXPECTED_ERROR)

async def update_email(user: User, update_data: user_schema.EmailUpdateRequest, db: AsyncSession) -> User:
    try:
        await verify_recaptcha(update_data.recaptcha_token)
        await check_verification_code_general(user, update_data.verificationCode)

        # Send confirmation email
        user_read = UserRead.model_validate(user)
        email_service = Email(user_read)
        email_service.send_email_changed_email(update_data.new_email)

        #TODO:We need to add confirm here,i.e. we need to send new code to varify the new E-maill and then he can use (Nayer)
        # Update local user
        user.email = update_data.new_email
        user.auth.verification_code = None
        user.auth.verification_code_exp = None
        await db.commit()
        await db.refresh(user)

        # Update microservices
        update_payload = user_schema.UserUpdate(email=update_data.new_email)
        await update_micro_services_users(user.user_id, update_payload)

        return user

    except HTTPException as e:
        await db.rollback()
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"{ErrorCode.UNEXPECTED_ERROR}: {str(e)}"
        )

async def confirm_email(user: User, code: user_schema.RegistrationConfirmation, db: AsyncSession) -> bool:
    try:
        await verify_recaptcha(code.recaptcha_token)
        await check_verification_code_general(user, code.verificationCode)
        user.auth.verification_code = None
        user.auth.verification_code_exp = None
        user.auth.email_confirmed = True


        # user_read = UserRead.model_validate(user)
        # email_service = Email(user_read)
        # email_service.send_complete_verification_email()

        await create_micro_services_users(UserCreate(
            account_id=user.user_id,
            account_id_hash=user.user_id_hash,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            profile_picture=user.profile_picture,
            date_of_birth=user.date_of_birth,
            gender=user.gender.value if user.gender else None,
            country_id=user.country_id,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=[role.value for role in user.roles],
        ),user.user_id, db)
        user.is_created = True
        await db.commit()
        await db.refresh(user)

        return True
    except HTTPException as e:
        await db.rollback()
        raise e
    except Exception as e:
        await db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{ErrorCode.UNEXPECTED_ERROR}: {str(e)}")

async def new_verification_code(user: User, db: AsyncSession) -> bool:
    new_code = await create_verification_code_general(user, db)
    return new_code

async def user_verification_code(user: User, user_data: user_schema.PasswordResetRequest, db: AsyncSession):
    try:
        await check_verification_code_general(user, user_data.verificationCode)

        if user_data.new_password != user_data.confirm_password:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ErrorCode.PASSWORDS_DONT_MATCH)

        if user.is_old:
            user.is_old=False
            user.auth.email_confirmed = True
            user.auth.hashed_password = generate_pass_hash(user_data.new_password)
            user.auth.verification_code = None
            user.auth.verification_code_exp = None

            await create_micro_services_users(UserCreate(
                account_id=user.user_id,
                account_id_hash=user.user_id_hash,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                profile_picture=user.profile_picture,
                date_of_birth=user.date_of_birth,
                gender=user.gender.value if user.gender else None,
                country_id=user.country_id,
                created_at=user.created_at,
                updated_at=user.updated_at,
                roles=[role.value for role in user.roles],
            ),user.user_id, db)
            user.is_created = True

        elif not user.is_created:
            user.auth.email_confirmed = True
            user.auth.hashed_password = generate_pass_hash(user_data.new_password)
            user.auth.verification_code = None
            user.auth.verification_code_exp = None

            await create_micro_services_users(UserCreate(
                account_id=user.user_id,
                account_id_hash=user.user_id_hash,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                profile_picture=user.profile_picture,
                date_of_birth=user.date_of_birth,
                gender=user.gender.value if user.gender else None,
                country_id=user.country_id,
                created_at=user.created_at,
                updated_at=user.updated_at,
                roles=[role.value for role in user.roles],
            ),user.user_id, db)
            user.is_created = True
        else:
            user.auth.email_confirmed = True
            user.auth.hashed_password = generate_pass_hash(user_data.new_password)
            user.auth.verification_code = None
            user.auth.verification_code_exp = None


        await db.commit()
        await db.refresh(user)

    except HTTPException as e:
        await db.rollback()
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{ErrorCode.UNEXPECTED_ERROR}: {str(e)}")

async def update_password_for_old_user(user: User, user_data: user_schema.PasswordResetRequest, db: AsyncSession):
    try:

        if user_data.new_password != user_data.confirm_password:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ErrorCode.PASSWORDS_DONT_MATCH)

        user.is_old=False
        user.auth.hashed_password = generate_pass_hash(user_data.new_password)
        await create_verification_code_general(user, db)
        verification_code = user.auth.verification_code

        ############ Send Email ################
        user_read = UserRead.model_validate(user)
        email_service = Email(user_read)
        email_service.send_registration_email(verification_code)
        ########################################

        await db.commit()
        await db.refresh(user)
        return user

    except HTTPException as e:
        await db.rollback()
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{ErrorCode.UNEXPECTED_ERROR}: {str(e)}")

async def send_email_with_vc_for_rest_password(user: User, db: AsyncSession) -> bool:
    await create_verification_code_general(user, db)

    user_read = UserRead.model_validate(user)
    email_service = Email(user_read)
    email_sent = email_service.send_password_reset_email(user.auth.verification_code)

    return email_sent

async def user_change_password(user: User, user_data: user_schema.NewPassword, db: AsyncSession):
    try:
        await verify_recaptcha(user_data.recaptcha_token)
        if user_data.new_password != user_data.confirm_password:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ErrorCode.PASSWORDS_DONT_MATCH)

        if not verify_hash_pass(user_data.old_password, user.auth.hashed_password):
            raise HTTPException(status_code=400, detail=ErrorCode.OLD_PASSWORD_INCORRECT)
        user.auth.hashed_password = generate_pass_hash(user_data.new_password)
        await db.commit()
        await db.refresh(user)

        ############ Send Email ################
        # user_read = UserRead.model_validate(user)
        # email_service = Email(user_read)
        # email_service.send_password_changed_email()
        ########################################

    except HTTPException as http_exc:
        raise http_exc
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail=ErrorCode.PASSWORD_CHANGE_ERROR)

#########################

async def get_device(request: Request):
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.ipify.org")

    # Get IP information
    client_ip = request.client.host  # Local IP, e.g., 192.168.1.3
    public_ip = response.text

    # Device detection
    user_agent_string = request.headers.get("User-Agent", "Unknown")
    user_agent = parse(user_agent_string)
    device_type = "MobilePhone" if user_agent.is_mobile else "PC" if user_agent.is_pc else "Other/Unknown"

    # Return response with IP
    return {
        "ip": client_ip,  # Local IP
        "device_type": device_type,
        "public_ip": public_ip  # Public IP, e.g., 156.205.224.28
    }

async def get_user_by_email(db: AsyncSession, email: EmailStr) -> Optional[User]:
    result = await db.execute(
        select(User)
        .options(selectinload(User.auth))
        .where(User.email == email, User.is_active == True)
    )
    return result.scalar_one_or_none()

async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
    result = await db.execute(
        select(User)
        .options(selectinload(User.auth))
        .filter(user_id == User.user_id, User.is_active == True)
    )
    user = result.scalars().first()
    return user

async def create_user(user_data: identity_service.schemas.user.UserCreate, db: AsyncSession) -> User:
    try:

        await verify_recaptcha(user_data.recaptcha_token)

        user_id = uuid.uuid4()
        str_user_id = str(user_id)
        hash_user_id = encryption_utility.encrypt(str_user_id)

        new_user = User(
            user_id=user_id,
            user_id_hash=hash_user_id,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            email=user_data.email,
            profile_picture=None,
            date_of_birth=user_data.date_of_birth,
            gender=user_data.gender,
            country_id=user_data.country_id,
            roles=[UserRole.SUBSCRIBER],
        )
        db.add(new_user)

        random_number = str(random.randint(100000, 999999))
        pass_hash = generate_pass_hash(user_data.password)
        ex_vc_date = datetime.now(tz=timezone.utc) + timedelta(minutes=1)

        new_user_auth = UserAuth(
            user_id=user_id,  # Use the same user_id
            hashed_password=pass_hash,
            verification_code=random_number,
            verification_code_exp=ex_vc_date,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        db.add(new_user_auth)
        await db.commit()
        await db.refresh(new_user)

        sync_records = []
        services = MsManager.get_services()

        for service_name, service_info in services.items():
            if service_info.create_async_user:  # use snake-case as per your enum key
                sync_record = MicroserviceSync(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    microservice=service_name,
                    url_prefix=service_info.url_prefix,
                    state=False,
                    created_at=datetime.now(tz=timezone.utc),
                    updated_at=datetime.now(tz=timezone.utc),
                    is_deleted=False
                )
                sync_records.append(sync_record)

        db.add_all(sync_records)
        await db.commit()
        await db.refresh(new_user)

        # Ensure relationship is explicitly set
        new_user.auth = new_user_auth
        await create_verification_code_general(new_user, db)

        ############ Send Email ################
        user_read = UserRead.model_validate(new_user)
        email_service = Email(user_read)
        email_service.send_registration_email(new_user_auth.verification_code)
        ########################################

        return new_user

    except HTTPException as e:
        await db.rollback()
        raise e
    except Exception as e:
        await db.rollback()
        raise e

async def update_user_name(user: User, update_data: user_schema.UserName, db: AsyncSession) -> User:
    user.first_name = update_data.first_name
    user.last_name = update_data.last_name
    await db.commit()
    await db.refresh(user)
    return user

async def update_status(user: User, db: AsyncSession):
    user.is_active = True
    ############ Send Email ################
    # user_read = UserRead.model_validate(user)
    # email_service = Email(user_read)
    # email_service.send_deactivation_email()
    ########################################
    await db.commit()
    await db.refresh(user)

async def update_profile(user: User, update_data: Union[dict, user_schema.UserUpdate], db: AsyncSession):
    # Handle both dict and Pydantic model inputs
    if isinstance(update_data, dict):
        data = update_data
    else:
        data = update_data.model_dump(exclude_unset=True)

    for key, value in data.items():
        # Store Enum values as strings in the model
        if isinstance(value, Enum):
            value = value.value
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)

    # Only call update_micro_services_users if a full Pydantic model is provided
    if not isinstance(update_data, dict):
        await update_micro_services_users(user.user_id, update_data)

    return user

async def update_user_role(user_id:UUID, admin_id:UUID, updated_role:UserRoleUpdate,  db: AsyncSession)-> User | None:
    admin = await get_user( db, str(admin_id))
    if not admin:
        raise HTTPException(status_code=403, detail=ErrorCode.USER_NOT_FOUND.value)
    if UserRole.ADMIN not in admin.roles:
        raise HTTPException(status_code=404, detail=ErrorCode.NOT_ADMIN.value)

    user = await get_user( db, str(user_id))
    if not user:
        raise HTTPException(status_code=404, detail=ErrorCode.USER_NOT_FOUND.value)
    if updated_role.roles is not None:
        user.roles = updated_role.roles
        user.updated_at = datetime.now()
        await db.commit()
        await db.refresh(user)

        # 4. Prepare payload for microservices sync
    update_payload = UserUpdate(roles=[role.value for role in user.roles] if user.roles else [])
    await update_micro_services_users(user.user_id, update_payload)

    return user

async def admin_user(user_id: uuid.UUID, db: AsyncSession) -> User:
    stmt = select(User).where(User.user_id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found_admin")
    if UserRole.ADMIN not in user.roles:
        raise HTTPException(status_code=403, detail="user_is_not_an_admin")
    return user

async def get_user(db: AsyncSession, user_id: str) -> Optional[User]:
    stmt = select(User).filter_by(user_id=user_id)
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_users(db: AsyncSession, skip: int, limit: int, search: str | None = None):
    stmt = select(User)

    # Apply search filter if provided
    if search:
        stmt = stmt.where(
            or_(
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    users = list(result.scalars().all())

    # Count total (with same filters if search applied)
    total_stmt = select(func.count()).select_from(User)
    if search:
        total_stmt = total_stmt.where(
            or_(
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )
    total = (await db.execute(total_stmt)).scalar_one()
    user_orm = [UserRead.model_validate(user) for user in users]
    return UsersRead(users=user_orm, total=total, skip=skip, limit=limit)


async def upload_profile_picture_helper(db: AsyncSession, user_id: UUID, profile_picture: UploadFile) -> str:
    try:
        user = await identity_service.services.auth.get_user_by_id(db, user_id)

        file_manager = FilesUtils(
            file_type=MongoDBChatMessageType.image,
            file=profile_picture,
            user=identity_service.schemas.user.UserRead.model_validate(user),
            file_source=CloudFlareFileSource.USER_PROFILE,
            bucket=CloudFlareR2Buckets.PUBLIC,
        )
        if shared_settings.ENVIRONMENT == "development":
            obj_name=f"dev/{str(user_id)}/public/profile/{uuid.uuid4()}"
        elif shared_settings.ENVIRONMENT == "local":
            obj_name=f"loc/{str(user_id)}/public/profile/{uuid.uuid4()}"
        else:
            obj_name = f"prod/{str(user_id)}/public/profile/{uuid.uuid4()}"
        # /2912bb20-ec16-4f14-b679-56bc60970190/public/identity-service/2912bb20-ec16-4f14-b679-56bc60970190.png
        if user.profile_picture:
            old_url = user.profile_picture
            await file_manager.delete_file(object_name= old_url)

        image_object_name = await file_manager.store_public_image_and_get_object_name(object_name=obj_name)
        profile_picture_url = f"{image_object_name}"

        user.profile_picture = profile_picture_url
        await db.commit()
        await db.refresh(user)

        # Update microservices
        update_payload = user_schema.UserUpdate(profile_picture=str(profile_picture_url))
        await update_micro_services_users(user.user_id, update_payload)

        return f"{shared_settings.THEOSUMMA_CDN_HOST}/{image_object_name}"
    except HTTPException as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error uploading profile picture: {str(e)}")


    #########################################################################

from dateutil import parser
from datetime import datetime, date, timezone

async def import_users_from_dataframe(df: pd.DataFrame, db: AsyncSession):
    users = []
    auths = []
    syncs = []

    # Fetch all existing emails in lowercase for consistency
    result = await db.execute(select(User.email))
    existing_emails = set(email.lower() for email in result.scalars().all() if email)

    for _, row in df.iterrows():
        email = row["Email"].lower()

        if email in existing_emails:
            print(f"Email {email} already exists. Skipping user.")
            continue

        user_id = uuid.uuid4()
        str_user_id = str(user_id)
        hash_user_id = encryption_utility.encrypt(str_user_id)
        now_utc = datetime.now(tz=timezone.utc)

        # Handle DOB
        raw_dob = row["DateOfBirth"]
        if pd.isna(raw_dob):
            date_of_birth = None
        elif isinstance(raw_dob, (datetime, date)):
            date_of_birth = raw_dob
        else:
            date_of_birth = parser.parse(str(raw_dob))

        # Create user object
        new_user = User(
            user_id=user_id,
            user_id_hash=hash_user_id,
            first_name=row["FirstName"],
            last_name=row["LastName"],
            email=email,
            profile_picture=None,
            date_of_birth=date_of_birth,
            gender=row["Gender"].upper(),
            is_old=True,
            country_id=row["CountryId"],
            created_at=now_utc,
            updated_at=now_utc,
            roles=[UserRole.SUBSCRIBER.value],
        )
        users.append(new_user)

        # Create sync records for this user
        for service_name, service_info in MsManager.get_services().items():
            if service_info.create_async_user:
                syncs.append(
                    MicroserviceSync(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        microservice=service_name,
                        url_prefix=service_info.url_prefix,
                        state=False,
                        created_at=now_utc,
                        updated_at=now_utc,
                        is_deleted=False,
                    )
                )

        # Create auth
        random_number = str(random.randint(100000, 999999))
        pass_hash = generate_pass_hash("rest_pass")
        new_user_auth = UserAuth(
            user_id=user_id,
            hashed_password=pass_hash,
            verification_code=random_number,
            verification_code_exp=now_utc + timedelta(minutes=1),
            created_at=now_utc,
            updated_at=now_utc,
        )
        auths.append(new_user_auth)

        # Update email set to prevent internal duplicates
        existing_emails.add(email)

    # Perform DB transaction
    async with db.begin():
        db.add_all(users)
        db.add_all(auths)
        db.add_all(syncs)

################################
async def register_white_user(email:str, db: AsyncSession):
    # Check environment
        whitelist_user = await db.execute(
            select(DevWhitelistUser).where(DevWhitelistUser.email == email)
        )
        result = whitelist_user.scalars().first()
        return result

async def add_white_user(email: str, db: AsyncSession) -> DevWhitelistUser:
    # Check if email already exists
    lower_email = email.lower()
    stmt = select(DevWhitelistUser).where(DevWhitelistUser.email == lower_email)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{lower_email}' is already whitelisted."
        )

    new_user = DevWhitelistUser(
        w_user_id=str(uuid.uuid4()),
        email=lower_email
    )

    db.add(new_user)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to insert user due to integrity error."
        )

    return new_user

async def delete_white_user(email: str, db: AsyncSession) -> DevWhitelistUser:
    # Check if email already exists
    lower_email = email.lower()
    stmt = select(DevWhitelistUser).where(DevWhitelistUser.email == lower_email)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{lower_email}' is Not whitelisted."
        )
    await db.delete(existing)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to insert user due to integrity error."
        )

    return f"Email '{lower_email}' is Deleted from whitelisted."



################################
async def social_login(request:Request, payload: SocialLoginRequest,
                       response: Response, db: AsyncSession) -> TokenData:
    try:
        provider = payload.provider
        access_token = payload.access_token
        user_info = None

        if provider == AuthProvider.GOOGLE:
            user_info = await verify_google_token(access_token)
            if not user_info:
                raise HTTPException(status_code=400, detail="Invalid Google token")

        if provider == AuthProvider.FACEBOOK:
            user_info = await verify_facebook_token(access_token)
            if not user_info:
                raise HTTPException(status_code=400, detail="Invalid Facebook token")

        if not user_info or not user_info.get("email"):
            raise HTTPException(status_code=400, detail="Missing user info")

        # Check if user exists
        user = await get_user_by_email(db, user_info["email"])

        if not user:
            # Register user (auto)
            user_id = uuid.uuid4()
            hash_user_id = encryption_utility.encrypt(str(user_id))

            user = User(
                user_id=user_id,
                user_id_hash=hash_user_id,
                email=user_info["email"],
                first_name=user_info["first_name"],
                last_name=user_info["last_name"],
                profile_picture=user_info["profile_picture"],
                roles=[UserRole.SUBSCRIBER],
                is_active=True,
            )
            db.add(user)

            auth = UserAuth(
                user_id=user_id,
                auth_provider=AuthProvider(provider.value),
                email_confirmed=True
            )
            db.add(auth)
            await db.commit()
            await db.refresh(user)

            # Sync to microservices
            await create_micro_services_users(UserCreate(
                account_id=user.user_id,
                account_id_hash=user.user_id_hash,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                profile_picture=user.profile_picture,
                date_of_birth=user.date_of_birth,
                gender=user.gender.value if user.gender else None,
                created_at=user.created_at,
                updated_at=user.updated_at,
                roles=[role.value for role in user.roles],
            ),user.user_id, db)

        # Return JWT
        user.auth.failed_login_attempts = 0
        user.auth.lockout_until = None
        current_time = datetime.now(tz=timezone.utc)
        user.last_login = current_time

        user_agent_string = request.headers.get("User-Agent", "Unknown")
        user_agent = parse(user_agent_string)
        device_type = DeviceType.MOBILE.value if user_agent.is_mobile else DeviceType.PC.value if user_agent.is_pc else DeviceType.UNKNOWN.value

        public_ip = await get_public_ip() or request.client.host

        jwt_id = uuid.uuid4()
        at_payload = AccessTokenPayload(user_id=str(user.user_id))
        rt_payload = RefreshTokenPayload(
            user_id=str(user.user_id),
            jwt_id=str(jwt_id),
            device_type=device_type
        )

        access_token = create_jwt_at_token(at_payload)
        new_refresh_token = create_jwt_rt_token(data=rt_payload, device_type=device_type)

        encrypted_refresh_token = encryption_utility.encrypt(new_refresh_token.jwt)

        await db.execute(delete(RefreshToken).where(
            RefreshToken.user_id == user.user_id,
            RefreshToken.device_type == device_type
        ))

        new_refresh_token_db = RefreshToken(
            jwt_id=jwt_id,
            user_id=user.user_id,
            hash_refresh_token=encrypted_refresh_token,
            public_ip=public_ip,
            device_type=device_type,
            refresh_token_exp=new_refresh_token.exp,
        )
        db.add(new_refresh_token_db)
        await db.commit()

        set_refresh_token_in_cookie(response=response, device_type=DeviceType(new_refresh_token_db.device_type),
                                    refresh_token=new_refresh_token.jwt)

        return TokenData(access_token=access_token)
    except HTTPException as e:
        await db.rollback()
        traceback.print_exc()
        raise e
    except Exception as e:
        await db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{ErrorCode.UNEXPECTED_ERROR}: {str(e)}")

async def admin_update_profile(user: User, update_data: Union[dict, user_schema.AdminUpdateUser], db: AsyncSession):
    # Handle both dict and Pydantic model inputs
    if isinstance(update_data, dict):
        data = update_data
    else:
        data = update_data.model_dump(exclude_unset=True)

    for key, value in data.items():
        # Convert Enum or List[Enum] to plain strings
        if isinstance(value, Enum):
            value = value.value
        elif isinstance(value, list):
            value = [v.value if isinstance(v, Enum) else v for v in value]

        setattr(user, key, value)

    # Only call update_micro_services_users if a full Pydantic model is provided
    if not isinstance(update_data, dict):
        await update_micro_services_users(user.user_id, update_data)

    await db.commit()
    await db.refresh(user)
    return user
