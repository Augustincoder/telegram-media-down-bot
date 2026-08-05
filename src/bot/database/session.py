import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base

# Ensure env variables are loaded (the user is preparing .env right now)
load_dotenv()

# Default to SQLite if not provided, exactly as requested
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_database.db")

# Create the async engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Session maker to be used in handlers or middleware
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_models():
    """
    Creates all tables in the database based on the models.
    This should be called during bot startup.
    """
    async with engine.begin() as conn:
        # For production with Alembic, we wouldn't use create_all()
        # but for this MVP SQLite setup it is perfectly fine.
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Dependency for getting DB session."""
    async with AsyncSessionLocal() as session:
        yield session
