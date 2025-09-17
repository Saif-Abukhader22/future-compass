import datetime
import uuid
from typing import Optional, List

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, Field, EmailStr, HttpUrl, field_validator

from identity_service.DB.enums import UserGender, UserRole, AuthProvider


class Country(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )
    country_id: int
    name: str
    code: str
    flag: str


class UserBase(BaseModel):
    model_config = ConfigDict(use_enum_values=True, from_attributes=True)
    first_name: str
    last_name: str
    email: EmailStr
    date_of_birth: Optional[datetime.datetime] = None
    gender: Optional[UserGender] = None
    country_id: Optional[int] = None
    roles: List[UserRole] = Field(default=[UserRole.SUBSCRIBER])

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

class UserCreate(UserBase):
    password: str
    recaptcha_token: str

class UserRead(UserBase):
    user_id: uuid.UUID
    profile_picture: Optional[str] = None  # Changed to str to avoid HttpUrl validation
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None
    country: Optional[Country] = Field(default_factory=lambda: None)

class UserReadForUpload(BaseModel):
    user_id: Optional[uuid.UUID] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    profile_picture: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    country_id: Optional[int] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    roles: Optional[list] = []
    country: Optional[str] = None

class FileProcessingUser(BaseModel):
    file: UploadFile

class UserCreateAdmin(UserBase):
    roles: List[UserRole] = Field(default=[UserRole.ADMIN])
    password_hash: str

class UserRoleUpdate(BaseModel):
    roles: Optional[List[UserRole]] = None


class UserStatus(BaseModel):
    is_deleted: str




class ContactUsCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    phone_number: Optional[str]= None
    message: str


class ContactUsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    submission_id: uuid.UUID
    response: str


class ContactUsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    message: str
    is_read: bool


class SocialLoginRequest(BaseModel):
    provider: AuthProvider
    access_token: str  # Facebook token

class UsersRead(BaseModel):
    users: List[UserRead] = []
    total: int
    skip: int
    limit: int


