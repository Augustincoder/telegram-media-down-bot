import asyncio
import logging
import os

from aiogram import Bot
from sqlalchemy.future import select

from bot.config import config
from bot.database.models import SavedProfile, StoryCache
from bot.database.session import AsyncSessionLocal
from bot.services.instagram import ig_service
from bot.services.telegram_userbot import userbot_service

logger = logging.getLogger(__name__)


async def start_story_monitor(bot: Bot):
    """
    Fon jarayoni:
    Har 2 soatda barcha SavedProfile larni aylanib chiqib, yangi hikoyalarni
    STORAGE_CHANNEL_ID ga tashlab qo'yadi.
    """
    if not config.storage_channel_id:
        logger.warning("STORAGE_CHANNEL_ID sozlanmagan. Story Monitor ishlamaydi.")
        return

    logger.info("Story monitor worker started...")

    # 2 soat (7200 soniya)
    POLL_INTERVAL = 7200

    while True:
        try:
            loop = asyncio.get_running_loop()

            async with AsyncSessionLocal() as session:
                # Barcha unikal profillarni platforma bilan birga olamiz
                result = await session.execute(
                    select(
                        SavedProfile.platform,
                        SavedProfile.ig_user_id,
                        SavedProfile.ig_username,
                    ).distinct()
                )
                profiles = result.all()

                for platform, ig_user_id, ig_username in profiles:
                    if not ig_username:
                        continue

                    if platform == "instagram":
                        if not ig_user_id:
                            continue
                        try:
                            stories = await loop.run_in_executor(
                                None, ig_service.client.user_stories, ig_user_id
                            )
                            
                            from bot.services.story_distributor import distribute_ig_stories
                            await distribute_ig_stories(
                                bot=bot,
                                session=session,
                                stories=stories,
                                username=ig_username,
                            )
                        except Exception as e:
                            logger.error(
                                f"Story Monitor IG {ig_username} uchun xatolik: {e}"
                            )
                            await asyncio.sleep(5)

                    elif platform == "telegram":
                        try:
                            stories = await userbot_service.get_peer_stories_info(
                                ig_username
                            )

                            from bot.services.story_distributor import distribute_tg_stories
                            await distribute_tg_stories(
                                bot=bot,
                                session=session,
                                stories=stories,
                                username=ig_username,
                            )
                        except Exception as e:
                            logger.error(
                                f"Story Monitor TG {ig_username} uchun xatolik: {e}"
                            )
                            await asyncio.sleep(5)

                    await asyncio.sleep(2)  # Profillar orasida biroz kutish

        except Exception as e:
            logger.error(f"Story Monitor iteratsiyasida xato: {e}")

        await asyncio.sleep(POLL_INTERVAL)
