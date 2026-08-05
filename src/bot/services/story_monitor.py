import asyncio
import logging

from aiogram import Bot
from sqlalchemy.future import select

from bot.config import config
from bot.database.models import SavedProfile, StoryCache
from bot.database.session import AsyncSessionLocal
from bot.services.instagram import ig_service

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
                # Barcha unikal IG user ID larni olish (bir xil profilni har xil odam saqlagan bo'lsa bitta qilib tekshiramiz)
                result = await session.execute(
                    select(SavedProfile.ig_user_id, SavedProfile.ig_username).distinct()
                )
                profiles = result.all()

                for ig_user_id, ig_username in profiles:
                    if not ig_user_id:
                        continue

                    try:
                        stories = await loop.run_in_executor(
                            None, ig_service.client.user_stories, ig_user_id
                        )

                        for story in stories:
                            story_pk = str(story.pk)

                            # Cache ni tekshiramiz
                            cache_res = await session.execute(
                                select(StoryCache).where(StoryCache.story_id == story_pk)
                            )
                            cached = cache_res.scalar_one_or_none()

                            if cached:
                                continue  # Allaqachon tortilgan

                            # Kanalga tashlaymiz
                            media_url = f"https://instagram.com/stories/{ig_username}/{story_pk}/"

                            from aiogram.types import BufferedInputFile

                            logger.info(f"Yangi hikoya topildi: {ig_username} -> {story_pk}")

                            async for item in ig_service.stream_instagram_media(media_url):
                                file = BufferedInputFile(
                                    item["data"],
                                    filename=f"story.{'mp4' if item['type'] == 'video' else 'jpg'}",
                                )

                                caption = f"📥 <b>{ig_username}</b> hikoyasi (Auto-Backup)"

                                sent_msg = None
                                if item["type"] == "video":
                                    sent_msg = await bot.send_video(
                                        config.storage_channel_id, file, caption=caption
                                    )
                                else:
                                    sent_msg = await bot.send_photo(
                                        config.storage_channel_id, file, caption=caption
                                    )

                                if sent_msg:
                                    # Keshga yozamiz
                                    new_cache = StoryCache(
                                        ig_username=ig_username,
                                        story_id=story_pk,
                                        telegram_msg_id=sent_msg.message_id,
                                    )
                                    session.add(new_cache)
                                    await session.commit()

                    except Exception as e:
                        logger.error(f"Story Monitor {ig_username} uchun xatolik: {e}")
                        await asyncio.sleep(5)  # Rate limit bo'lsa biroz kutamiz

                    await asyncio.sleep(2)  # Profillar orasida biroz kutish

        except Exception as e:
            logger.error(f"Story Monitor iteratsiyasida xato: {e}")

        await asyncio.sleep(POLL_INTERVAL)
