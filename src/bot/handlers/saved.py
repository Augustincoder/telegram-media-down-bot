import asyncio
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
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


@router.message(Command("save"))
async def save_profile_handler(message: Message, session: AsyncSession):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "❌ Noto'g'ri format! /save ig @username yoki /save tg @username"
        )
        return

    platform = "instagram"
    username = ""

    if len(parts) >= 3 and parts[1].lower() in ["ig", "tg"]:
        platform = "instagram" if parts[1].lower() == "ig" else "telegram"
        username = parts[2].replace("@", "")
    else:
        username = extract_username(message.text)
        if not username:
            await message.answer("❌ Noto'g'ri format!")
            return

    user_id = message.from_user.id

    result = await session.execute(
        select(SavedProfile).where(SavedProfile.user_id == user_id)
    )
    saved_profiles = result.scalars().all()

    if len(saved_profiles) >= 10:
        await message.answer(
            "❌ Limit tugadi! Siz maksimal 10 ta profil saqlay olasiz."
        )
        return

    for p in saved_profiles:
        if p.ig_username.lower() == username.lower() and p.platform == platform:
            await message.answer("✅ Bu profil allaqachon saqlangan.")
            return

    wait_msg = await message.answer(
        f"🔍 <b>@{username}</b> ({platform}) qidirilmoqda..."
    )

    try:
        if platform == "instagram":
            loop = asyncio.get_running_loop()
            user_info = await loop.run_in_executor(
                None, ig_service.client.user_info_by_username, username
            )
            ig_user_id = str(user_info.pk)
            username = user_info.username
        else:
            peer = await userbot_service.client.get_entity(username)
            ig_user_id = str(peer.id)
            username = getattr(peer, "username", username)

        new_profile = SavedProfile(
            user_id=user_id,
            ig_username=username,
            ig_user_id=ig_user_id,
            platform=platform,
        )
        session.add(new_profile)
        await session.commit()

        await wait_msg.edit_text(
            f"✅ <b>@{username}</b> muvaffaqiyatli saqlandi! Ularni ko'rish uchun /saved ni bosing."
        )
    except Exception as e:
        await wait_msg.edit_text(f"❌ Profilni topib bo'lmadi yoki xatolik: {e}")


@router.message(Command("saved"))
async def list_saved_profiles(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    result = await session.execute(
        select(SavedProfile).where(SavedProfile.user_id == user_id)
    )
    profiles = result.scalars().all()

    if not profiles:
        await message.answer(
            "Sizda hech qanday saqlangan profil yo'q. /save orqali qo'shing."
        )
        return

    wait_msg = await message.answer("⏳ Saqlangan profillar ro'yxati tayyorlanmoqda...")

    keyboard = []

    for p in profiles:
        emoji = "📸" if p.platform == "instagram" else "✈️"
        text = f"{emoji} @{p.ig_username}"
        keyboard.append(
            [InlineKeyboardButton(text=text, callback_data=f"get_story_{p.id}")]
        )

    keyboard.append(
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="refresh_saved")]
    )

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await wait_msg.edit_text("⭐ <b>Saqlangan profillaringiz:</b>", reply_markup=markup)


@router.callback_query(F.data == "refresh_saved")
async def refresh_saved(callback: CallbackQuery, session: AsyncSession):
    await list_saved_profiles(callback.message, session)
    await callback.answer()


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
