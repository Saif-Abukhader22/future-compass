from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from identity_service.DB import Country


async def get_all_countries(db: AsyncSession) -> Sequence[Country]:
    results = await db.execute(
        select(Country)
    )
    return results.scalars().all()

async def get_country_by_id(db: AsyncSession, country_id: int) -> Country:
    result = await db.execute(
        select(Country).where(Country.country_id == country_id)
    )
    return result.scalar_one_or_none()