# app/schemas/user.py
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from datetime import datetime

from shared.enums import SubscriptionPlanEnum


class UserSubscriptionBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )
    """
    subscription_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey('users.user_id', ondelete="CASCADE", name='user_subscriptions_user_id_fkey'),
        nullable=False,
        unique=True
    )
    plan_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey('plans.plan_id', ondelete="SET NULL", name='user_subscriptions_plan_id_fkey'),
        nullable=False,
    )
    subscription_start = Column(DateTime, nullable=False, default=datetime.datetime.now(datetime.UTC))
    subscription_end = Column(DateTime, nullable=True)
    points_balance = Column(Integer, nullable=False, default=0)
    collected_points = Column(Integer, nullable=False, default=0)  # Points bought separately
    """
    user_id: uuid.UUID
    plan_id: uuid.UUID
    subscription_start: datetime
    subscription_end: datetime | None
    points_balance: int
    collected_points: int


class UserSubscriptionRead(UserSubscriptionBase):
    subscription_id: uuid.UUID


class UserSubscriptionUpdate(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values = True
    )
    plan_id: uuid.UUID
    subscription_start: datetime
    subscription_end: datetime | None
    subscription_duration: Optional[SubscriptionPlanEnum] = SubscriptionPlanEnum.MONTHLY


class UserRemainingPoints(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )
    total_points: int
    remaining_points: int
