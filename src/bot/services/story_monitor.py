import asyncio
import logging

from aiogram import Bot
from sqlalchemy.future import select

from bot.config import config
from bot.database.models import SavedProfile
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

    import random
    
    while True:
        POLL_INTERVAL = random.randint(3600, 5400) # 1 to 1.5 hours
        try:
            loop = asyncio.get_running_loop()
            profiles = []

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(
                        SavedProfile.platform,
                        SavedProfile.ig_user_id,
                        SavedProfile.ig_username,
                        SavedProfile.tg_access_hash,
                    ).distinct()
                )
                profiles = result.all()

            for platform, ig_user_id, ig_username, tg_access_hash in profiles:
                if not ig_username:
                    continue

                if platform == "instagram":
                    if not ig_user_id:
                        continue
                    try:
                        # Timeout to prevent thread pool exhaustion
                        stories = await asyncio.wait_for(
                            loop.run_in_executor(
                                None, ig_service.client.user_stories, ig_user_id
                            ),
                            timeout=30.0
                        )
                        
                        from bot.services.story_distributor import distribute_ig_stories
                        async with AsyncSessionLocal() as session:
                            await distribute_ig_stories(
                                bot=bot,
                                session=session,
                                stories=stories,
                                username=ig_username,
                            )
                    except Exception as e:
                        err_msg = str(e).lower()
                        if "user_has_logged_out" in err_msg or "login_required" in err_msg or "403" in err_msg or "invalid request" in err_msg:
                            ig_service.is_logged_in = False

                        logger.error(f"Story Monitor IG {ig_username} uchun xatolik: {e}")
                        
                        if not ig_service.is_logged_in:
                            logger.warning("Story monitor: Session expired. Attempting to re-login...")
                            async with AsyncSessionLocal() as session:
                                success = await ig_service.login(
                                    session=session,
                                    username=config.instagram_username,
                                    password=config.instagram_password,
                                    session_id=config.instagram_session_id
                                )
                            if not success:
                                logger.error("Auto re-login failed in story monitor. Pausing for 5 mins.")
                                await asyncio.sleep(300)
                                break  # Stop checking this round

                    # Random kutish Instagram shubxasini yo'qotish uchun
                    await asyncio.sleep(random.randint(60, 120))

                elif platform == "telegram":
                    try:
                        # Timeout for TG requests
                        stories = await asyncio.wait_for(
                            userbot_service.get_peer_stories_info(
                                ig_username, access_hash=tg_access_hash
                            ),
                            timeout=20.0
                        )

                        from bot.services.story_distributor import distribute_tg_stories
                        async with AsyncSessionLocal() as session:
                            await distribute_tg_stories(
                                bot=bot,
                                session=session,
                                stories=stories,
                                username=ig_username,
                                access_hash=tg_access_hash,
                            )
                    except Exception as e:
                        logger.error(
                            f"Story Monitor TG {ig_username} uchun xatolik: {e}"
                        )
                    await asyncio.sleep(10)

        except Exception as e:
            logger.error(f"Story Monitor iteratsiyasida xato: {e}")

        await asyncio.sleep(POLL_INTERVAL)
