import logging
import uuid
from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession

from identity_service.DB.models.users import MicroserviceSync, User
from shared.enums import MicroServiceName
from shared.ts_ms.ms_manager import MsManager
from shared.users_sync import schema as users_sync_schema
from identity_service.utils.Error_Handling import ErrorCode

logger = logging.getLogger(__name__)



async def create_micro_services_users(create_user_data: users_sync_schema.UserCreate,
user_id: UUID,
        db: AsyncSession
):
    try:
        services = MsManager.get_services()

        for service_name, service_info in services.items():
            if service_name == MicroServiceName.IDENTITY_SERVICE.snake():
                continue  # Skip the identity service

            if not service_info.active or not service_info.create_async_user:
                logger.info(f"Skipping inactive or non-async-enabled service: {service_name}")
                continue

            logger.info(f"Starting user sync with microservice: {service_name}")

            # Step 1: Check if user exists
            try:
                await MsManager.get(
                    service_name=service_name,
                    endpoint=f"/accounts/{create_user_data.account_id}",
                    base_error_message=f"Error checking user in microservice {service_name}"
                )
                logger.info(f"User already exists in microservice {service_name}, skipping creation")
                continue

            except httpx.ConnectError as conn_err:
                logger.warning(f"Could not connect to {service_name}: {conn_err}")
                continue

            except HTTPException as check_error:
                if check_error.status_code == 500:
                    logger.warning(f"Service {service_name} is unavailable (500). Skipping.")
                    continue
                elif check_error.status_code != 404:
                    logger.error(f"Unexpected error checking user in {service_name}: {check_error}")
                    raise check_error
                # 404 means user not found → proceed to create

            # Step 2: Create user in microservice
            try:
                response = await MsManager.post(
                    service_name=service_name,
                    endpoint="/accounts/",
                    base_error_message=f"Error creating user in microservice {service_name}",
                    json=create_user_data.model_dump(exclude_unset=True),
                )

                try:
                    new_user_data = response.json()
                except Exception as parse_error:
                    logger.error(f"Failed to parse JSON response from {service_name}: {parse_error}")
                    logger.error(f"Raw response text: {response.text}")
                    raise HTTPException(status_code=500, detail=ErrorCode.INVALID_JSON_RESPONSE_MICROSERVICE.value)

                if not new_user_data:
                    logger.error(f"No user created in microservice {service_name}")
                    raise HTTPException(status_code=500, detail=ErrorCode.ERROR_SYNCING_USER.value)

                logger.info(f"User created in microservice {service_name}")

                # Step 3: Update MicroserviceSync state
                result = await db.scalar(
                    select(MicroserviceSync).where(
                        MicroserviceSync.user_id == user_id,
                        MicroserviceSync.microservice == service_name
                    )
                )

                if result:
                    stmt = (
                        update(MicroserviceSync)
                        .where(
                            MicroserviceSync.user_id == user_id,
                            MicroserviceSync.microservice == service_name
                        )
                        .values(
                            state=True,
                            updated_at=datetime.now(tz=timezone.utc)
                        )
                    )
                    await db.execute(stmt)
                    await db.commit()
                    logger.info(f"Updated MicroserviceSync for {service_name}")
                else:
                    logger.warning(f"No MicroserviceSync entry found for {service_name} and user {user_id}")

            except httpx.ConnectError as conn_err:
                logger.warning(f"Could not connect to {service_name} during user creation: {conn_err}")
                continue

            except HTTPException as create_error:
                logger.error(f"Error creating user in microservice {service_name}: {create_error}")
                if create_error.status_code in [404, 500]:
                    logger.warning(f"Microservice {service_name} returned {create_error.status_code}. Skipping.")
                    continue
                raise create_error

        await db.commit()

    except HTTPException as e:
        raise e

    except Exception as e:
        logger.error(f"Error syncing users with microservices: {str(e)}")
        raise HTTPException(status_code=500, detail=ErrorCode.ERROR_SYNCING_USERS_MICROSERVICES.value)



async def update_micro_services_users(
    user_id: UUID,
    update_user_data: users_sync_schema.UserUpdate
):
    try:
        from shared.ts_ms.ms_manager import MsManager
        # Convert HttpUrl to string for profile_picture before sending it
        if update_user_data.profile_picture:
            update_user_data.profile_picture = str(update_user_data.profile_picture)

        for service_name, service_info in MsManager.get_services().items():
            if service_name == MicroServiceName.IDENTITY_SERVICE.snake() or not service_info.active:
                continue
            if not service_info.active or not service_info.create_async_user:
                logger.info(f"Skipping inactive or non-async-enabled service: {service_name}")
                continue

            logger.info("starting syncing user with microservice " + service_name)
            try:
                response = await MsManager.put(
                    service_name=service_name,
                    endpoint=f"/accounts/{user_id}",
                    base_error_message="Error updating user in microservice " + service_name,
                    json=update_user_data.model_dump(exclude_unset=True, mode="json")
                )

                try:
                    updated_user_data = response.json()
                    logger.info(f"User updated in microservice {service_name}")
                    if not updated_user_data:
                        logger.error("No user updated in microservice " + service_name)
                        raise HTTPException(status_code=500, detail="Error syncing user")
                except Exception as parse_error:
                    logger.error(f"Failed to parse JSON response from {service_name}: {parse_error}")
                    logger.error(f"Raw response text: {response.text}")
                    raise HTTPException(status_code=500, detail=ErrorCode.INVALID_JSON_RESPONSE_MICROSERVICE.value)

            except HTTPException as e:
                logger.error(f"!!!!! Error updating user in microservice {service_name}: {str(e)}")
                if e.status_code == 404:
                    logger.warning(f"Microservice {service_name} not found")
                    continue
                else:
                    raise e
    except Exception as main_error:
        logger.error(f"Error syncing users with microservices: {main_error}")
        raise HTTPException(status_code=500, detail=ErrorCode.INTERNAL_ERROR_SYNCING_USER_MICROSERVICES.value)


async def check_all_micro_services_accounts(db: AsyncSession):
    now_utc = datetime.now(tz=timezone.utc)
    services = MsManager.get_services()

    # Get all user IDs
    user_ids = (await db.execute(select(User.user_id))).scalars().all()

    syncs_to_add = []

    for service_name, service_info in services.items():
        if not service_info.create_async_user:
            continue

        for user_id in user_ids:
            # Check if MicroserviceSync already exists
            existing_sync = await db.scalar(
                select(MicroserviceSync).where(
                    MicroserviceSync.user_id == user_id,
                    MicroserviceSync.microservice == service_name
                )
            )

            if existing_sync:
                continue

            logger.info(f"Adding missing MicroserviceSync for user {user_id} and service {service_name}")

            syncs_to_add.append(
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

    if syncs_to_add:
        db.add_all(syncs_to_add)
        await db.commit()
        logger.info(f"Added {len(syncs_to_add)} missing MicroserviceSync records.")
    else:
        logger.info("All MicroserviceSync records are already up to date.")

async def create_user_in_specific_microservice(
    create_user_data: users_sync_schema.UserCreate,
    user_id: UUID,
    db: AsyncSession,
    target_service_name: str
):
    try:
        # Normalize the service name
        target_service_name = target_service_name.strip().lower()
        services = MsManager.get_services()

        if target_service_name == MicroServiceName.IDENTITY_SERVICE.snake():
            logger.info("Skipping identity service as target microservice")
            return

        service_info = services.get(target_service_name)
        if not service_info:
            logger.error(f"Microservice {target_service_name} not found in configuration")
            raise HTTPException(status_code=404, detail=f"Microservice {target_service_name} not found")

        if not service_info.active or not service_info.create_async_user:
            logger.info(f"Microservice {target_service_name} is inactive or does not support async user creation")
            return

        logger.info(f"Starting user sync with microservice: {target_service_name}")

        # Step 1: Check if user already exists
        try:
            await MsManager.get(
                service_name=target_service_name,
                endpoint=f"/accounts/{create_user_data.account_id}",
                base_error_message=f"Error checking user in microservice {target_service_name}"
            )
            logger.info(f"User already exists in microservice {target_service_name}, updating MicroserviceSync state")

            # ✅ Update MicroserviceSync state to True if user already exists
            result = await db.scalar(
                select(MicroserviceSync).where(
                    MicroserviceSync.user_id == user_id,
                    MicroserviceSync.microservice == target_service_name
                )
            )

            if result:
                stmt = (
                    update(MicroserviceSync)
                    .where(
                        MicroserviceSync.user_id == user_id,
                        MicroserviceSync.microservice == target_service_name
                    )
                    .values(
                        state=True,
                        updated_at=datetime.now(tz=timezone.utc)
                    )
                )
                await db.execute(stmt)
                logger.info(f"Updated MicroserviceSync for {target_service_name} (user already existed)")
            else:
                new_sync = MicroserviceSync(
                    user_id=user_id,
                    microservice=target_service_name,
                    state=True,
                    updated_at=datetime.now(tz=timezone.utc)
                )
                db.add(new_sync)
                logger.info(f"Created new MicroserviceSync for {target_service_name} (user already existed)")

            await db.commit()
            return

        except httpx.ConnectError as conn_err:
            logger.warning(f"Could not connect to {target_service_name}: {conn_err}")
            return

        except HTTPException as check_error:
            if check_error.status_code == 500:
                logger.warning(f"Service {target_service_name} is unavailable (500). Skipping.")
                return
            elif check_error.status_code != 404:
                logger.error(f"Unexpected error checking user in {target_service_name}: {check_error}")
                raise check_error
            # 404 means user not found → proceed to create

        # Step 2: Create user in microservice
        try:
            response = await MsManager.post(
                service_name=target_service_name,
                endpoint="/accounts/",
                base_error_message=f"Error creating user in microservice {target_service_name}",
                json=create_user_data.model_dump(exclude_unset=True),
            )

            try:
                new_user_data = response.json()
            except Exception as parse_error:
                logger.error(f"Failed to parse JSON response from {target_service_name}: {parse_error}")
                logger.error(f"Raw response text: {response.text}")
                raise HTTPException(status_code=500, detail=ErrorCode.INVALID_JSON_RESPONSE_MICROSERVICE.value)

            if not new_user_data:
                logger.error(f"No user created in microservice {target_service_name}")
                raise HTTPException(status_code=500, detail=ErrorCode.ERROR_SYNCING_USER.value)

            logger.info(f"User created in microservice {target_service_name}")

            # Step 3: Update or insert MicroserviceSync state
            result = await db.scalar(
                select(MicroserviceSync).where(
                    MicroserviceSync.user_id == user_id,
                    MicroserviceSync.microservice == target_service_name
                )
            )

            if result:
                stmt = (
                    update(MicroserviceSync)
                    .where(
                        MicroserviceSync.user_id == user_id,
                        MicroserviceSync.microservice == target_service_name
                    )
                    .values(
                        state=True,
                        updated_at=datetime.now(tz=timezone.utc)
                    )
                )
                await db.execute(stmt)
                logger.info(f"Updated MicroserviceSync for {target_service_name}")
            else:
                new_sync = MicroserviceSync(
                    user_id=user_id,
                    microservice=target_service_name,
                    state=True,
                    updated_at=datetime.now(tz=timezone.utc)
                )
                db.add(new_sync)
                logger.info(f"Created new MicroserviceSync entry for {target_service_name} and user {user_id}")

            await db.commit()

        except httpx.ConnectError as conn_err:
            logger.warning(f"Could not connect to {target_service_name} during user creation: {conn_err}")

        except HTTPException as create_error:
            logger.error(f"Error creating user in microservice {target_service_name}: {create_error}")
            if create_error.status_code in [404, 500]:
                logger.warning(f"Microservice {target_service_name} returned {create_error.status_code}. Skipping.")
                return
            raise create_error

    except HTTPException as e:
        raise e

    except Exception as e:
        logger.error(f"Error syncing user with microservice {target_service_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=ErrorCode.ERROR_SYNCING_USERS_MICROSERVICES.value)
