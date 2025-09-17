from uuid import UUID

from pydantic import BaseModel, EmailStr, HttpUrl, Field, ConfigDict, field_validator
from typing import List, Optional


from shared.enums import UserRole, UserGender
import datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    user_id: str | None = None
    iat: datetime.datetime | None = None
    exp: datetime.datetime | None = None
    token_type: str | None = None


class AccessTokenPayload(BaseModel):
    user_id: str


class RefreshTokenPayload(BaseModel):
    user_id: str
    jwt_id: str
    device_type: str


class NewRefreshToken(BaseModel):
    jwt: str
    exp: datetime.datetime | None = None


class PasswordResetRequest(BaseModel):
    email: EmailStr
    verificationCode: str
    new_password: str
    confirm_password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

class PasswordResetRequestForOld(BaseModel):
    email: EmailStr
    new_password: str
    confirm_password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()



class EmailUpdateRequest(BaseModel):
    recaptcha_token: str
    email: EmailStr
    verificationCode: str
    new_email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("new_email")
    @classmethod
    def normalize_new_email(cls, v: str) -> str:
        return v.strip().lower()

class RegistrationConfirmation(BaseModel):
    recaptcha_token: str
    email: EmailStr
    verificationCode: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class EmailData(BaseModel):
    recaptcha_token: str
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class NewPassword(BaseModel):
    new_password: str
    old_password: str


    confirm_password: str
    recaptcha_token: str


class LoginData(BaseModel):
    username: str
    password: str
    # recaptcha_token: str


class TokenData(BaseModel):
    access_token: str


class ResponseMessage(BaseModel):
    message: str


# if settings.ENVIRONMENT == 'local':
#     password_hash: str


# class EmailUpdate(BaseModel):
#     verificationCode: str
#     email: EmailStr
#     newEmail: EmailStr
#
#     @field_validator("email")
#     @classmethod
#     def normalize_email(cls, v: str) -> str:
#         return v.strip().lower()

class UserName(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

class NewAccessToken(BaseModel):
    new_access_token: str

class UserUpdatePassword(BaseModel):
    password_hash: str

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_picture: Optional[str] = None
    date_of_birth: Optional[datetime.datetime] = None
    gender: Optional[UserGender] = None
    country_id: Optional[int] = None

class AdminUpdateUser(UserUpdate):
    roles: Optional[List[UserRole]] = Field(default_factory=list)

class ErrorDate(BaseModel):
    path: str
    exception: str
    traceback: str
class ErrorResponse(BaseModel):
    error_id: UUID
    path: str
    exception: str
    traceback: str
    time: datetime.datetime