from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from identity_service.DB.models.users import MicroserviceSync, User
from shared import shared_settings
from shared.users_sync import schema as users_sync_schema
from identity_service.DB.database import AsyncSessionLocal
from identity_service.services.users import (
    check_all_micro_services_accounts,
    create_user_in_specific_microservice,
    update_micro_services_users
)
import logging

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def run_check_all_micro_services_accounts():
    async with AsyncSessionLocal() as db:
        await check_all_micro_services_accounts(db)
        await run_create_pending_microservice_users(db)


async def run_create_pending_microservice_users(db: AsyncSession):
    all_syncs = (
        await db.execute(
            select(MicroserviceSync)
        )
    ).scalars().all()

    if not all_syncs:
        logger.info("No MicroserviceSync entries found.")
        return

    for sync in all_syncs:
        user = await db.scalar(select(User).where(User.user_id == sync.user_id))
        if not user:
            logger.warning(f"User {sync.user_id} not found. Skipping.")
            continue

        user_data = users_sync_schema.UserCreate(
            account_id=user.user_id,
            account_id_hash=user.user_id_hash,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            profile_picture=str(user.profile_picture) if user.profile_picture else None,
            date_of_birth=user.date_of_birth,
            gender=user.gender.value if user.gender else None,
            country_id=user.country_id,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=[role.value for role in user.roles],
        )

        try:
            # If user not created yet, create it
            if not sync.state:
                await create_user_in_specific_microservice(
                    create_user_data=user_data,
                    user_id=sync.user_id,
                    db=db,
                    target_service_name=sync.microservice,
                )
            else:
                pass
                # Otherwise update the user
                # update_data = users_sync_schema.UserUpdate(**user_data.model_dump())
                # await update_micro_services_users(
                #     user_id=sync.user_id,
                #     update_user_data=update_data
                # )
                # logger.info(f"Updated user {sync.user_id} in microservice {sync.microservice}")
        except Exception as e:
            logger.error(f"Error syncing user {sync.user_id} to {sync.microservice}: {e}")

print(shared_settings.ENVIRONMENT)
if (shared_settings.ENVIRONMENT == 'production'
        or shared_settings.ENVIRONMENT == 'development'
):

    def start_cron_jobs():
        try:
            scheduler.add_job(
                func=run_check_all_micro_services_accounts,
                trigger=IntervalTrigger(hours=24),  # every 24 hours from startup time
                name="Check all MicroserviceSync and then sync users",
                replace_existing=True,
            )
            scheduler.start()
            logger.info("Cron job scheduled to run every 24 hours.")
        except JobLookupError as e:
            logger.error(f"Failed to schedule job: {e}")
else:
    def start_cron_jobs():
        try:
            scheduler.add_job(
                func=run_check_all_micro_services_accounts,
                trigger=IntervalTrigger(minutes=120),  # every 24 minutes from startup time
                name="Check all MicroserviceSync and then sync users",
                replace_existing=True,
            )
            scheduler.start()
            logger.info("Cron job scheduled to run every 15 minutes.")
        except JobLookupError as e:
            logger.error(f"Failed to schedule job: {e}")
