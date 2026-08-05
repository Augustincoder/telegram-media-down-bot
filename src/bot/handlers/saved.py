import asyncio
import re

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.config import config
from bot.database.models import SavedProfile, StoryCache
from bot.services.instagram import ig_service
from bot.services.telegram_userbot import userbot_service

router = Router()


def extract_username(text: str) -> str | None:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None
    raw = parts[1].strip()
    if "instagram.com" in raw:
        match = re.search(r"instagram\.com/([^/?]+)", raw)
        if match:
            return match.group(1)
    return raw.replace("@", "")


@router.callback_query(F.data.startswith("get_story_"))
async def process_story_request(callback: CallbackQuery, session: AsyncSession):
    profile_id = int(callback.data.split("_")[2])

    result = await session.execute(
        select(SavedProfile).where(SavedProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    emoji = "📸" if profile.platform == "instagram" else "✈️"
    await callback.answer(f"@{profile.ig_username} hikoyalari olinmoqda...")
    await callback.message.answer(
        f"📥 <b>@{profile.ig_username} {emoji}</b> hikoyalari tortilmoqda..."
    )

    loop = asyncio.get_running_loop()
    try:
        if profile.platform == "instagram":
            stories = await loop.run_in_executor(
                None, ig_service.client.user_stories, profile.ig_user_id
            )
            if not stories:
                await callback.message.answer(
                    f"❌ <b>@{profile.ig_username}</b> hozirda hech qanday hikoya joylamagan."
                )
                return

            bot = callback.bot
            for story in stories:
                story_pk = str(story.pk)
                cache_res = await session.execute(
                    select(StoryCache).where(
                        StoryCache.story_id == story_pk,
                        StoryCache.platform == "instagram",
                    )
                )
                cached = cache_res.scalar_one_or_none()
                if cached and config.storage_channel_id:
                    try:
                        await bot.copy_message(
                            chat_id=callback.from_user.id,
                            from_chat_id=config.storage_channel_id,
                            message_id=cached.telegram_msg_id,
                        )
                        continue
                    except Exception:
                        pass

                media_url = (
                    f"https://instagram.com/stories/{profile.ig_username}/{story_pk}/"
                )
                from aiogram.types import BufferedInputFile

                async for item in ig_service.stream_instagram_media(media_url):
                    file = BufferedInputFile(
                        item["data"],
                        filename=f"story.{'mp4' if item['type'] == 'video' else 'jpg'}",
                    )
                    if item["type"] == "video":
                        await bot.send_video(callback.from_user.id, file)
                    else:
                        await bot.send_photo(callback.from_user.id, file)

        elif profile.platform == "telegram":
            stories = await userbot_service.get_peer_stories_info(profile.ig_username)
            if not stories:
                await callback.message.answer(
                    f"❌ <b>@{profile.ig_username}</b> hozirda hech qanday hikoya joylamagan."
                )
                return

            bot = callback.bot
            import os

            for story in stories:
                story_id = str(story.id)
                cache_res = await session.execute(
                    select(StoryCache).where(
                        StoryCache.story_id == story_id,
                        StoryCache.platform == "telegram",
                    )
                )
                cached = cache_res.scalar_one_or_none()
                if cached and config.storage_channel_id:
                    try:
                        await bot.copy_message(
                            chat_id=callback.from_user.id,
                            from_chat_id=config.storage_channel_id,
                            message_id=cached.telegram_msg_id,
                        )
                        continue
                    except Exception:
                        pass

                file_path = f"downloads/tg_story_{profile.ig_username}_{story_id}.mp4"
                os.makedirs("downloads", exist_ok=True)
                try:
                    downloaded = await userbot_service.download_story(
                        profile.ig_username, story.id, file_path
                    )
                    if downloaded:
                        from aiogram.types import FSInputFile

                        media = FSInputFile(downloaded)
                        if downloaded.endswith(".mp4"):
                            await bot.send_video(callback.from_user.id, media)
                        else:
                            await bot.send_photo(callback.from_user.id, media)
                finally:
                    import contextlib

                    with contextlib.suppress(OSError):
                        if os.path.exists(file_path):
                            os.remove(file_path)

    except Exception as e:
        await callback.message.answer(f"❌ Xatolik yuz berdi: {e}")
