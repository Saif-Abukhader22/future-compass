import uuid

from fastapi import HTTPException
import traceback
from shared.schemas.core.user import UserSubscriptionRead, UserSubscriptionUpdate
from shared.users_sync import SessionDep
from shared.users_sync.ms_specific.core_service import update_user_subscription
from shared.users_sync.router import user_sync_router
from shared.users_sync.service import get_user
from shared.utils.logger import TsLogger
logger = TsLogger(name=__name__)


@user_sync_router.put("/{account_id}/subscription", response_model=UserSubscriptionRead)
async def update_account_subscription(
        account_id: uuid.UUID,
        subscription_update: UserSubscriptionUpdate,
        db: SessionDep
) -> UserSubscriptionRead:
    try:

        user = await get_user(db, account_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        updated_subscription = await update_user_subscription(user, subscription_update, db)
        if updated_subscription is None:
            raise HTTPException(status_code=404, detail="Subscription not found or not active Testing")
        return UserSubscriptionRead.model_validate(updated_subscription)
    except HTTPException as e:
        traceback.print_exc()
        raise e
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

