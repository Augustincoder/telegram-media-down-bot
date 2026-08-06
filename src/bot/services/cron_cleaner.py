import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from bot.database.models import Download, StoryCache
from bot.database.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def start_cron_cleaner():
    """
    Fon jarayoni:
    Har 24 soatda ma'lumotlar bazasidan 30 kundan eski bo'lgan
    StoryCache va Download yozuvlarini tozalaydi.
    """
    logger.info("Cron cleaner worker started...")
    
    # 24 soat (86400 soniya)
    CLEANUP_INTERVAL = 86400
    DAYS_TO_KEEP = 30
    
    while True:
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=DAYS_TO_KEEP)
            
            async with AsyncSessionLocal() as session:
                # Delete old StoryCache
                # Note: StoryCache uses added_at
                story_result = await session.execute(
                    delete(StoryCache).where(StoryCache.added_at < cutoff_date)
                )
                
                # Delete old Download
                download_result = await session.execute(
                    delete(Download).where(Download.downloaded_at < cutoff_date)
                )
                
                await session.commit()
                
                deleted_stories = story_result.rowcount
                deleted_downloads = download_result.rowcount
                
                if deleted_stories > 0 or deleted_downloads > 0:
                    logger.info(f"Cron Cleanup: {deleted_stories} ta eski story kesh, {deleted_downloads} ta eski download kesh o'chirildi.")
        
        except Exception as e:
            logger.error(f"Cron cleaner ishida xatolik: {e}")
            
        await asyncio.sleep(CLEANUP_INTERVAL)
