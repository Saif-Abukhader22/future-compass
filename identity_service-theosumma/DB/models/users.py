import uuid

from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, Integer, ARRAY, func, Index, desc
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from identity_service.DB.database import Base
from identity_service.DB.enums import UserGender, UserRole, AuthProvider


class User(Base):
    __tablename__ = "users"

    user_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    user_id_hash = Column(String, nullable=True, unique=True)  # Hashed user ID for security that used on Other MS
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    profile_picture = Column(String, nullable=True)  # URL to user's avatar
    date_of_birth = Column(DateTime(timezone=True), nullable=True)
    phone_number = Column(String, nullable=True, default=None) #add phone Number
    gender = Column(Enum(UserGender), nullable=True)
    is_old = Column(Boolean,nullable=True, default=False)
    is_created = Column(Boolean,nullable=True, default=False)
    # TODO: when sending the country of the user, you need to send the country object in the response schema
    country_id = Column(Integer, ForeignKey("countries.country_id", name="users_country_id_fky", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)  # Account status
    last_login = Column(DateTime(timezone=True), nullable=True)  # Last login timestamp

    # Roles field as an array of UserRole enum
    roles = Column(ARRAY(Enum(UserRole)), nullable=False, default=[UserRole.SUBSCRIBER])

    # Relationships
    auth = relationship("UserAuth", uselist=False, back_populates="user", lazy='selectin', cascade="all, delete-orphan")
    country = relationship("Country", lazy='selectin')
    refresh_tokens = relationship("RefreshToken", back_populates="user", lazy='dynamic')
    messages = relationship("ContactUsSubmission", back_populates="user", lazy='selectin', cascade="all, delete-orphan", order_by=lambda: desc(ContactUsSubmission.created_at))


class UserAuth(Base):
    __tablename__ = "user_auth"

    uid = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.user_id", name="user_auth_users_fky" ,ondelete="CASCADE"), nullable=False, unique=True)
    auth_provider = Column(Enum(AuthProvider), nullable=False,
                           default=AuthProvider.LOCAL)  # Local, Google, Facebook, etc.
    hashed_password = Column(String, nullable=True)  # NULL if using external auth providers

    verification_code = Column(String, nullable=True)
    verification_code_exp = Column(DateTime(timezone=True), nullable=True)
    email_confirmed = Column(Boolean, nullable=False, default=False)

    # TODO: (later) implement lockout mechanism to prevent dictionary attacks
    failed_login_attempts = Column(Integer, nullable=False, default=0)  # Prevent brute-force attacks
    lockout_until = Column(DateTime(timezone=True), nullable=True)  # Account lockout time



    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), default=func.now())

    # Relationship to User table
    user = relationship("User", back_populates="auth", uselist=False, lazy='selectin')

class Country(Base):
    __tablename__ = "countries"

    country_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    code = Column(String, nullable=False, unique=True, index=True)
    flag = Column(String, nullable=False)
    calling_code = Column(String, nullable=False)

    # Relationships
    users = relationship("User", back_populates="country", lazy='select')  # Changed to 'select'

class RefreshToken(Base):
    """This table stores data used to revoke and refresh database sessions or tokens."""
    __tablename__ = "refresh_tokens"

    __table_args__ = (
        Index('ix_rt_user_id', 'user_id'), # index over the user_id to improve query performance
    )

    jwt_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.user_id", name="user_auth_users_fky" ,ondelete="CASCADE"), nullable=False)
    device_type = Column(String, nullable=False)
    hash_refresh_token = Column(String, nullable=False, index=True) # Refresh token for JWT authentication
    refresh_token_exp = Column(DateTime(timezone=True), nullable=True)  # Expiration of refresh token
    public_ip = Column(String, nullable=False)
    is_blackList = Column(Boolean, nullable= False, default= False)

    issued_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), default=func.now())




    # Relationships
    user = relationship("User", back_populates="refresh_tokens", uselist=False, lazy='select')  # Fixed relationship


class DevWhitelistUser(Base):
    __tablename__ = 'dev_whitelist_users'

    w_user_id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)


class ContactUsSubmission(Base):
    __tablename__ = "contact_us_submission"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.user_id", name="user_auth_users_fky", ondelete="CASCADE"), nullable=False)
    message = Column(String, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    user = relationship("User", back_populates="messages", uselist=False, lazy='selectin')

class MicroserviceSync(Base):
    __tablename__ = "microservice_sync"
    id= Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    user_id=Column(PGUUID(as_uuid=True), ForeignKey("users.user_id", name="user_auth_users_fky", ondelete="CASCADE"), nullable=False)
    microservice=Column(String, nullable=False)
    url_prefix=Column(String, nullable=False)
    state = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
