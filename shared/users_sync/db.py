import os
import uuid

from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer, ARRAY, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from shared.users_sync import Base
from shared.enums import UserGender, UserRole, MicroServiceName

"""
!!! Important !!!
This model should not be included for the identity service.
This model is used among other services to link users with their accounts.
"""

current_microservice_name = os.environ["CURRENT_MICRO_SERVICE_NAME"]

class User(Base):
    __tablename__ = "users"

    user_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    account_id = Column(PGUUID(as_uuid=True), unique=True, nullable=False)
    account_id_hash = Column(String, nullable=True, unique=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    profile_picture = Column(String, nullable=True)  # URL to user's avatar
    date_of_birth = Column(DateTime(timezone=True), nullable=True)
    gender = Column(Enum(UserGender), nullable=True)
    country_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)

    # Roles field as an array of UserRole enum
    roles = Column(ARRAY(Enum(UserRole)), nullable=False, default=[UserRole.SUBSCRIBER])

    # Relationships
    if current_microservice_name == MicroServiceName.CORE_SERVICE:
        subscription = relationship("UserSubscription", uselist=False, back_populates="user", lazy='selectin')
        threads = relationship("Thread", back_populates="user", lazy='selectin')
        api_requests = relationship("APIRequest", back_populates="user", lazy='selectin')
        thread_folders = relationship("ThreadFolder", back_populates="user", lazy='selectin')
        feature_usages = relationship("FeatureUsage", back_populates="user", lazy='selectin')
        audio_transcriptions = relationship("AudioTranscription", back_populates="user", lazy='selectin')
    elif current_microservice_name == MicroServiceName.SUBSCRIPTION_SERVICE:
        subscriptions = relationship("Subscription", back_populates="user")
        card_details = relationship("CardDetails", back_populates="user")
        checkouts = relationship("Checkout", back_populates="user")
        transactions = relationship("Transaction", back_populates="user")
        coupon_usages = relationship("CouponUsage", back_populates="user", lazy="selectin")
        payment_response = relationship("PaymentResponseModel", back_populates="user", uselist=True)
        cancellation_transactions = relationship("CancellationTransaction", back_populates="user", lazy="selectin")
    elif current_microservice_name == MicroServiceName.COMMUNITY_SERVICE:
        posts = relationship("Post", back_populates="user", lazy='selectin')
        comments = relationship("Comment", back_populates="user", lazy='selectin')
        replies = relationship("Reply", back_populates="user", lazy='selectin')
        invitations = relationship("PostInvitation", back_populates="user", lazy='selectin')
        approval_requests = relationship("PostApprovalRequest", back_populates="user", lazy='selectin', cascade="all, delete-orphan")
        activities = relationship("Activity", back_populates="user", lazy='selectin')
        notifications = relationship("Notification", back_populates="user", lazy='selectin')
    elif current_microservice_name == MicroServiceName.DOC_CHATTING_SERVICE:
            documents = relationship("Document", back_populates="user", lazy="selectin")
    elif current_microservice_name == MicroServiceName.BIBLE_SERVICE:
        pass
    elif current_microservice_name == MicroServiceName.ASSESSMENTS_SERVICE:
        assessment_sessions = relationship("UserSession", back_populates="user")
    elif current_microservice_name == MicroServiceName.NOTIFICATIONS_SERVICE:
        notifications = relationship("Notification", back_populates="user")
        devices = relationship("UserDevice", back_populates="user", cascade="all, delete-orphan")

