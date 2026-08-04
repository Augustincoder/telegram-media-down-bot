import asyncio
from bot.database.models import Base
from bot.database.session import engine

async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Migrated successfully!")

if __name__ == "__main__":
    asyncio.run(migrate())
