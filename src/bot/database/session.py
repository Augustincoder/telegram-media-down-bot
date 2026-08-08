from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import config

from .models import Base

# Ensure env variables are loaded (the user is preparing .env right now)
load_dotenv()

# Only PostgreSQL is supported for production
DATABASE_URL = config.database_url

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith(
    "postgresql+asyncpg://"
):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

if "postgresql+asyncpg://" in DATABASE_URL and "sslmode=" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("sslmode=", "ssl=")
# Create the async engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Session maker to be used in handlers or middleware
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_models():
    """
    Creates all tables in the database based on the models.
    This should be called during bot startup.
    """
    async with engine.begin() as conn:
        # For production with Alembic, we wouldn't use create_all()
        await conn.run_sync(Base.metadata.create_all)
        
    # Run the migration in a separate transaction so a failure doesn't rollback create_all
    async with engine.begin() as conn:
        try:
            from sqlalchemy import text
            # Ignore errors (like duplicate column)
            await conn.execute(text("ALTER TABLE saved_profiles ADD COLUMN tg_access_hash VARCHAR"))
        except Exception:
            pass
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE saved_profiles ADD COLUMN last_checked_at TIMESTAMP WITH TIME ZONE DEFAULT '1970-01-01 00:00:00+00'"))
        except Exception:
            pass


async def get_session() -> AsyncSession:
    """Dependency for getting DB session."""
    async with AsyncSessionLocal() as session:
        yield session
