import asyncio
import logging
import random
from datetime import datetime

from aiogram import Bot
from sqlalchemy.future import select

from bot.database.models import HighlightTask, SavedProfile, StoryCache
from bot.database.session import AsyncSessionLocal
from bot.services.instagram import ig_service
from bot.services.telegram_userbot import userbot_service

logger = logging.getLogger(__name__)


async def _process_ig_highlight_batch(bot: Bot):
    async with AsyncSessionLocal() as session:
        # Get up to 10 pending IG tasks
        result = await session.execute(
            select(HighlightTask)
            .where(HighlightTask.platform == "instagram", HighlightTask.status == "PENDING")
            .limit(10)
        )
        tasks = result.scalars().all()

        if not tasks:
            return False  # No tasks

        logger.info(f"[Highlight Engine IG] Processing {len(tasks)} tasks.")

        for task in tasks:
            try:
                # Check deduplication
                cache_check = await session.execute(
                    select(StoryCache).where(
                        StoryCache.story_id == task.story_id, StoryCache.platform == "instagram"
                    )
                )
                if cache_check.scalar_one_or_none():
                    task.status = "DONE"
                    task.processed_at = datetime.now()
                    await session.commit()
                    continue

                # Profilni olish
                prof_res = await session.execute(
                    select(SavedProfile).where(SavedProfile.id == task.profile_id)
                )
                profile = prof_res.scalar_one_or_none()
                if not profile:
                    task.status = "FAILED"
                    await session.commit()
                    continue

                # 1 API chaqiruv orqali story metadata sini olish
                loop = asyncio.get_running_loop()
                story = await loop.run_in_executor(
                    None, ig_service.client.story_info, task.story_id
                )

                # Yuklash (distribute funksiyasidan foydalanamiz, target_chat_id None berilsa faqat kanalga saqlaydi)
                from bot.services.story_distributor import distribute_ig_stories

                await distribute_ig_stories(
                    bot=bot,
                    session=session,
                    stories=[story],
                    username=profile.ig_username,
                    target_chat_id=None,
                    status_msg=None,
                )

                task.status = "DONE"
                task.processed_at = datetime.now()
                await session.commit()

            except Exception as e:
                logger.error(f"[Highlight Engine IG] Task {task.id} failed: {e}")
                task.status = "FAILED"
                task.processed_at = datetime.now()
                await session.commit()

            # Har bir hikoyadan keyin kutish (bot sezilib qolmasligi uchun)
            await asyncio.sleep(random.randint(45, 90))

        return True


async def start_ig_highlight_worker(bot: Bot):
    logger.info("Instagram Highlight Worker started.")
    while True:
        try:
            has_tasks = await _process_ig_highlight_batch(bot)

            if has_tasks:
                # Agar vazifa bo'lsa, yana yuklash uchun 1-2 soat kutamiz
                sleep_time = random.randint(3600, 7200)
                logger.info(f"[Highlight Engine IG] Batch done. Sleeping {sleep_time}s.")
                await asyncio.sleep(sleep_time)
            else:
                # Agar vazifa yo'q bo'lsa, har 30 daqiqada tekshirib turamiz
                await asyncio.sleep(1800)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[Highlight Engine IG] Worker error: {e}")
            await asyncio.sleep(300)


async def _process_tg_highlight_batch(bot: Bot):
    if not userbot_service.is_connected:
        return False

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(HighlightTask)
            .where(HighlightTask.platform == "telegram", HighlightTask.status == "PENDING")
            .limit(10)
        )
        tasks = result.scalars().all()

        if not tasks:
            return False

        logger.info(f"[Highlight Engine TG] Processing {len(tasks)} tasks.")

        # TG da barchasini bittada olish uchun hikoyalarni profil bo'yicha guruhlaymiz
        profile_tasks = {}
        for t in tasks:
            if t.profile_id not in profile_tasks:
                profile_tasks[t.profile_id] = []
            profile_tasks[t.profile_id].append(t)

        for profile_id, p_tasks in profile_tasks.items():
            try:
                prof_res = await session.execute(
                    select(SavedProfile).where(SavedProfile.id == profile_id)
                )
                profile = prof_res.scalar_one_or_none()
                if not profile:
                    for t in p_tasks:
                        t.status = "FAILED"
                    await session.commit()
                    continue

                story_ids = [int(t.story_id) for t in p_tasks]

                # Fetch story info using GetStoriesByIDRequest
                from telethon.tl.functions.stories import GetStoriesByIDRequest

                peer_id = (
                    int(profile.ig_user_id)
                    if profile.ig_user_id.lstrip("-").isdigit()
                    else profile.ig_user_id
                )
                if isinstance(peer_id, int) and profile.tg_access_hash:
                    from telethon.tl.types import InputPeerChannel, InputPeerUser, InputPeerChat

                    acc_hash = int(profile.tg_access_hash)
                    if peer_id < 0:
                        s_id = str(peer_id)
                        if s_id.startswith("-100"):
                            entity = InputPeerChannel(channel_id=int(s_id[4:]), access_hash=acc_hash)
                        else:
                            entity = InputPeerChat(chat_id=int(s_id[1:]))
                    else:
                        entity = InputPeerUser(user_id=peer_id, access_hash=acc_hash)
                else:
                    try:
                        entity = await userbot_service.client.get_input_entity(peer_id)
                    except ValueError:
                        entity = await userbot_service.client.get_input_entity(profile.ig_username)

                result_stories = await userbot_service.client(
                    GetStoriesByIDRequest(peer=entity, id=story_ids)
                )

                if result_stories.stories:
                    from bot.services.story_distributor import distribute_tg_stories

                    await distribute_tg_stories(
                        bot=bot,
                        session=session,
                        stories=result_stories.stories,
                        username=profile.ig_username,
                        target_chat_id=None,
                        status_msg=None,
                        peer_id=profile.ig_user_id,
                        access_hash=profile.tg_access_hash,
                    )

                for t in p_tasks:
                    t.status = "DONE"
                    t.processed_at = datetime.now()
                await session.commit()

            except Exception as e:
                logger.error(f"[Highlight Engine TG] Profile {profile_id} tasks failed: {e}")
                for t in p_tasks:
                    t.status = "FAILED"
                    t.processed_at = datetime.now()
                await session.commit()

            await asyncio.sleep(5)  # TG limitlari yumshoqroq

        return True


async def start_tg_highlight_worker(bot: Bot):
    logger.info("Telegram Highlight Worker started.")
    while True:
        try:
            has_tasks = await _process_tg_highlight_batch(bot)

            if has_tasks:
                # Telegram u qadar qattiq block qimaydi, har 10 daqiqada keyingi batch
                logger.info("[Highlight Engine TG] Batch done. Sleeping 600s.")
                await asyncio.sleep(600)
            else:
                await asyncio.sleep(600)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[Highlight Engine TG] Worker error: {e}")
            await asyncio.sleep(60)
