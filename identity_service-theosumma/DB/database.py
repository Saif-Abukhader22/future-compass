"""Database configuration for the identity service."""

from sqlalchemy.ext.declarative import declarative_base

from identity_service.config import settings
from shared import db_manager

# Define your database connection URL (change to async URL)
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine, AsyncSessionLocal = db_manager.create_engine_from_settings(settings)
get_db = db_manager.get_db

Base = declarative_base()
