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

                            for story in stories:
                                story_pk = str(story.pk)

                                cache_res = await session.execute(
                                    select(StoryCache).where(
                                        StoryCache.story_id == story_pk,
                                        StoryCache.platform == "instagram",
                                    )
                                )
                                cached = cache_res.scalar_one_or_none()
                                if cached:
                                    continue  # Allaqachon tortilgan

                                from aiogram.types import BufferedInputFile

                                logger.info(
                                    f"Yangi IG hikoya topildi: {ig_username} -> {story_pk}"
                                )

                                media_items = []
                                if story.media_type == 1:
                                    media_items.append(
                                        {"type": "photo", "url": str(story.thumbnail_url)}
                                    )
                                elif story.media_type == 2:
                                    media_items.append({"type": "video", "url": str(story.video_url)})

                                async for item in ig_service._stream_media_items_concurrently(
                                    media_items
                                ):
                                    file = BufferedInputFile(
                                        item["data"],
                                        filename=f"story.{'mp4' if item['type'] == 'video' else 'jpg'}",
                                    )
                                    caption = f"📥 <b>{ig_username} 📸</b> hikoyasi (Auto-Backup)"

                                    sent_msg = None
                                    if item["type"] == "video":
                                        sent_msg = await bot.send_video(
                                            config.storage_channel_id,
                                            file,
                                            caption=caption,
                                        )
                                    else:
                                        sent_msg = await bot.send_photo(
                                            config.storage_channel_id,
                                            file,
                                            caption=caption,
                                        )

                                    if sent_msg:
                                        new_cache = StoryCache(
                                            platform="instagram",
                                            ig_username=ig_username,
                                            story_id=story_pk,
                                            telegram_msg_id=sent_msg.message_id,
                                        )
                                        session.add(new_cache)
                                        await session.commit()
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

                            for story in stories:
                                story_id = str(story.id)

                                cache_res = await session.execute(
                                    select(StoryCache).where(
                                        StoryCache.story_id == story_id,
                                        StoryCache.platform == "telegram",
                                    )
                                )
                                cached = cache_res.scalar_one_or_none()
                                if cached:
                                    continue

                                logger.info(
                                    f"Yangi TG hikoya topildi: {ig_username} -> {story_id}"
                                )

                                file_path = f"downloads/auto_tg_story_{ig_username}_{story_id}.mp4"
                                os.makedirs("downloads", exist_ok=True)

                                try:
                                    downloaded = await userbot_service.download_story(
                                        ig_username, story.id, file_path
                                    )
                                    if downloaded:
                                        from aiogram.types import FSInputFile

                                        media = FSInputFile(downloaded)
                                        caption = f"📥 <b>{ig_username} ✈️</b> hikoyasi (Auto-Backup)"

                                        sent_msg = None
                                        if downloaded.endswith(".mp4"):
                                            sent_msg = await bot.send_video(
                                                config.storage_channel_id,
                                                media,
                                                caption=caption,
                                            )
                                        else:
                                            sent_msg = await bot.send_photo(
                                                config.storage_channel_id,
                                                media,
                                                caption=caption,
                                            )

                                        if sent_msg:
                                            new_cache = StoryCache(
                                                platform="telegram",
                                                ig_username=ig_username,
                                                story_id=story_id,
                                                telegram_msg_id=sent_msg.message_id,
                                            )
                                            session.add(new_cache)
                                            await session.commit()
                                finally:
                                    import contextlib

                                    with contextlib.suppress(OSError):
                                        if os.path.exists(file_path):
                                            os.remove(file_path)

                        except Exception as e:
                            logger.error(
                                f"Story Monitor TG {ig_username} uchun xatolik: {e}"
                            )
                            await asyncio.sleep(5)

                    await asyncio.sleep(2)  # Profillar orasida biroz kutish

        except Exception as e:
            logger.error(f"Story Monitor iteratsiyasida xato: {e}")

        await asyncio.sleep(POLL_INTERVAL)
