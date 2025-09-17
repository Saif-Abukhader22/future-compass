from pydantic import BaseModel, EmailStr, HttpUrl, Field, ConfigDict
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from shared.enums import UserRole, UserGender


class UserBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True
    )

    account_id: UUID
    account_id_hash: Optional[str] = None
    first_name: str
    last_name: str
    email: EmailStr
    profile_picture: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    gender: Optional[UserGender] = None
    country_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    roles: List[UserRole] = Field(default=[UserRole.SUBSCRIBER])


class UserCreate(UserBase):
    pass


class UserRead(UserBase):
    user_id: UUID


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    # email: Optional[EmailStr] = None
    profile_picture: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    gender: Optional[UserGender] = None
    country_id: Optional[int] = None
    roles: Optional[List[UserRole]] = Field(default_factory=list)

    class Config:
        use_enum_values = True

