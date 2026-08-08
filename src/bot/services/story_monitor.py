import asyncio
import logging
import random
from datetime import datetime, timezone

from aiogram import Bot
from sqlalchemy import func
from sqlalchemy.future import select

from bot.config import config
from bot.database.models import SavedProfile
from bot.database.session import AsyncSessionLocal
from bot.services.instagram import ig_service
from bot.services.telegram_userbot import userbot_service

logger = logging.getLogger(__name__)


async def update_last_checked(session, profile_id):
    profile = await session.get(SavedProfile, profile_id)
    if profile:
        profile.last_checked_at = func.now()
        await session.commit()


async def ig_monitor_worker(bot: Bot):
    logger.info("Instagram story monitor worker started...")
    loop = asyncio.get_running_loop()
    
    while True:
        try:
            # Kutish: 1 soatdan 2 soatgacha
            await asyncio.sleep(random.randint(3600, 7200))
            
            profiles = []
            async with AsyncSessionLocal() as session:
                # Har safar eng eski tekshirilgan 10 ta profilni olamiz
                result = await session.execute(
                    select(SavedProfile)
                    .where(SavedProfile.platform == "instagram")
                    .order_by(SavedProfile.last_checked_at.asc().nullsfirst())
                    .limit(10)
                )
                profiles = result.scalars().all()

            for profile in profiles:
                if not profile.ig_user_id or not profile.ig_username:
                    continue

                try:
                    stories = await asyncio.wait_for(
                        loop.run_in_executor(
                            None, ig_service.client.user_stories, profile.ig_user_id
                        ),
                        timeout=30.0
                    )
                    
                    from bot.services.story_distributor import distribute_ig_stories
                    async with AsyncSessionLocal() as session:
                        await distribute_ig_stories(
                            bot=bot,
                            session=session,
                            stories=stories,
                            username=profile.ig_username,
                        )
                        await update_last_checked(session, profile.id)

                except Exception as e:
                    err_msg = str(e).lower()
                    if "user_has_logged_out" in err_msg or "login_required" in err_msg or "403" in err_msg or "invalid request" in err_msg:
                        ig_service.is_logged_in = False

                    logger.error(f"Story Monitor IG {profile.ig_username} uchun xatolik: {e}")
                    
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

                # Har bir profil orasida 1 daqiqa kutish (shubhani yo'qotish uchun)
                await asyncio.sleep(60)
                
        except Exception as e:
            logger.error(f"IG Story Monitor iteratsiyasida xato: {e}")
            await asyncio.sleep(60)


async def tg_monitor_worker(bot: Bot):
    logger.info("Telegram story monitor worker started...")
    
    while True:
        try:
            # Kutish: 10 daqiqa
            await asyncio.sleep(600)
            
            profiles = []
            async with AsyncSessionLocal() as session:
                # Har safar eng eski tekshirilgan 10 ta profilni olamiz
                result = await session.execute(
                    select(SavedProfile)
                    .where(SavedProfile.platform == "telegram")
                    .order_by(SavedProfile.last_checked_at.asc().nullsfirst())
                    .limit(10)
                )
                profiles = result.scalars().all()

            for profile in profiles:
                if not profile.ig_username:
                    continue

                try:
                    # Timeout for TG requests
                    stories = await asyncio.wait_for(
                        userbot_service.get_peer_stories_info(
                            profile.ig_user_id or profile.ig_username, access_hash=profile.tg_access_hash
                        ),
                        timeout=20.0
                    )

                    from bot.services.story_distributor import distribute_tg_stories
                    async with AsyncSessionLocal() as session:
                        await distribute_tg_stories(
                            bot=bot,
                            session=session,
                            stories=stories,
                            username=profile.ig_username,
                            peer_id=profile.ig_user_id,
                            access_hash=profile.tg_access_hash,
                        )
                        await update_last_checked(session, profile.id)
                except Exception as e:
                    logger.error(
                        f"Story Monitor TG {profile.ig_username} uchun xatolik: {e}"
                    )
                
                # Telegram uchun qisqa 10 soniya kutish
                await asyncio.sleep(10)

        except Exception as e:
            logger.error(f"TG Story Monitor iteratsiyasida xato: {e}")
            await asyncio.sleep(60)


async def start_story_monitor(bot: Bot):
    """
    Fon jarayoni:
    Instagram uchun har soat-ikki soatda 10ta profilni tekshiradi, oraliq 1 daqiqa.
    Telegram uchun har 10 daqiqada 10ta profilni tekshiradi.
    """
    if not config.storage_channel_id:
        logger.warning("STORAGE_CHANNEL_ID sozlanmagan. Story Monitor ishlamaydi.")
        return

    logger.info("Starting separate background tasks for IG and TG story monitors...")
    
    asyncio.create_task(ig_monitor_worker(bot))
    asyncio.create_task(tg_monitor_worker(bot))
