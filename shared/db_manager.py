from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine, async_sessionmaker

engine: Optional[AsyncEngine] = None
AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None


def create_engine_from_settings(settings) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    global engine, AsyncSessionLocal

    url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(
        url,
        pool_size=int(getattr(settings, "POOL_SIZE", 10)),
        max_overflow=int(getattr(settings, "MAX_OVERFLOW", 20)),
        pool_timeout=int(getattr(settings, "POOL_TIMEOUT", 30)),
        pool_recycle=int(getattr(settings, "POOL_RECYCLE", 300)),
        pool_pre_ping=True,
        pool_use_lifo=True,          # new
        echo_pool=getattr(settings, "DEBUG_SQL", False),
    )

    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autoflush=False,
        expire_on_commit=False,
        # autocommit removed → don't pass it
    )

    return engine, AsyncSessionLocal


async def get_db():
    if AsyncSessionLocal is None:
        raise RuntimeError("Engine not initialised")

    async with AsyncSessionLocal() as session:
        try:
            yield session          # let the request handler run
            await session.commit() # commit if no error
        except Exception:
            await session.rollback()
            raise



async def close_engine() -> None:
    """Dispose of the configured engine."""
    if engine is not None:
        await engine.dispose()
