import datetime
import os

from fastapi import HTTPException

from core_service.DB.enums import PlatformPlans
from shared.enums import MicroServiceName, SubscriptionPlanEnum
from shared.errors.core import CoreErrors
from shared.schemas.core.user import UserSubscriptionUpdate
from datetime import timedelta
from shared.utils.logger import TsLogger

logger = TsLogger(name=__name__)

if "CURRENT_MICRO_SERVICE_NAME" not in os.environ:
    raise ValueError("CURRENT_MICRO_SERVICE_NAME environment variable is not set")

if os.environ['CURRENT_MICRO_SERVICE_NAME'] == MicroServiceName.CORE_SERVICE:
    from uuid import UUID

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from shared.users_sync.db import User
    from core_service.DB import UserSubscription, Plan


    async def get_user_subscription(db: AsyncSession, user_id: UUID) -> UserSubscription | None:
        stmt = select(UserSubscription).where(UserSubscription.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


    async def create_user_subscription(new_user: User, db: AsyncSession) -> UserSubscription:
        stmt = select(Plan).where(Plan.name == PlatformPlans.FREE)
        result = await db.execute(stmt)
        plan = result.scalar_one_or_none()

        subscription = UserSubscription(
            user_id=new_user.user_id,
            plan_id=plan.plan_id,
            subscription_start=new_user.created_at,
            subscription_end= new_user.created_at + timedelta(days=30)   ,
            points_balance=plan.points,
        )
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)
        return subscription


    async def update_user_subscription(
            user: User,
            subscription_update: UserSubscriptionUpdate,
            db: AsyncSession
    ) -> UserSubscription | None:
        stmt = select(UserSubscription).where(UserSubscription.user_id == user.user_id)
        subscription_query = await db.execute(stmt)
        subscription = subscription_query.scalar_one_or_none()


        stmt_plan = select(Plan).where(subscription_update.plan_id == Plan.plan_id)
        result_plan = await db.execute(stmt_plan)
        plan = result_plan.scalars().first()
        if not plan:
            raise HTTPException(status_code=404, detail="This Plan Not Exist In Core MS Tables")

        if subscription and plan:
            subscription.plan_id = plan.plan_id
            subscription.subscription_start = subscription_update.subscription_start
            subscription.subscription_end = subscription_update.subscription_end
            if subscription_update.subscription_duration == SubscriptionPlanEnum.MONTHLY.value:
                subscription.points_balance = plan.points
            elif subscription_update.subscription_duration == SubscriptionPlanEnum.ANNUAL.value:
                subscription.points_balance = plan.points * 12
            else:
                raise HTTPException(status_code=400, detail=CoreErrors.INVALID_SUBSCRIPTION_DURATION)
            await db.commit()
            await db.refresh(subscription)
            return subscription
        return None