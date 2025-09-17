import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.sql import text

from identity_service.main import app
from identity_service.DB.database import Base
from identity_service.DB import get_db

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5438/postgres"
)

@pytest.fixture(scope="session")
def engine():
    return create_async_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
        echo=True,  # Helpful for debugging
        connect_args={
            "server_settings": {
                "jit": "off",
                "statement_timeout": "5000"
            }
        }
    )

@pytest.fixture(scope="session")
async def setup_db(engine):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS test"))
        await conn.execute(text("SET search_path TO test, public"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP SCHEMA IF EXISTS test CASCADE"))

@pytest.fixture
def session_factory(engine, setup_db):
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession
    )

@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        await session.execute(text("SET search_path TO test, public"))
        async with session.begin():
            yield session


@pytest.fixture
def test_client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            await session.execute(text("SET search_path TO test, public"))
            async with session.begin():
                yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

@pytest.fixture
def random_email():
    import uuid
    return f"test_{uuid.uuid4().hex}@example.com"