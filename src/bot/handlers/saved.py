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

from bot.database.models import SavedProfile
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
async def list_saved_profiles(
    message: Message, session: AsyncSession, user_id: int | None = None
):
    if user_id is None:
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

    wait_msg = await message.answer(
        "⏳ Saqlangan profillarning hikoyalari tekshirilmoqda..."
    )

    keyboard = []
    loop = asyncio.get_running_loop()

    for p in profiles:
        emoji = "📸" if p.platform == "instagram" else "✈️"
        try:
            if p.platform == "instagram":
                stories = await loop.run_in_executor(
                    None, ig_service.client.user_stories, p.ig_user_id
                )
                has_story = len(stories) > 0
            else:
                stories = await userbot_service.get_peer_stories_info(p.ig_user_id or p.ig_username)
                has_story = bool(stories)

            icon = "🟢" if has_story else "⚪"
            text = f"{icon} {emoji} @{p.ig_username}"
        except Exception:
            text = f"⚠️ {emoji} @{p.ig_username}"

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
    import contextlib
    with contextlib.suppress(Exception):
        await callback.message.delete()
    await list_saved_profiles(
        callback.message, session, user_id=callback.from_user.id
    )
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
    status_msg = await callback.message.answer(
        f"🔍 <b>@{profile.ig_username} {emoji}</b> hikoyalari izlanmoqda..."
    )

    loop = asyncio.get_running_loop()
    try:
        if profile.platform == "instagram":
            stories = await loop.run_in_executor(
                None, ig_service.client.user_stories, profile.ig_user_id
            )
        else:
            stories = await userbot_service.get_peer_stories_info(profile.ig_user_id or profile.ig_username)

        if not stories:
            await status_msg.edit_text(
                f"❌ <b>@{profile.ig_username} {emoji}</b> hozirda hech qanday hikoya joylamagan."
            )
            return

        total = len(stories)
        bot = callback.bot
        from bot.services.story_distributor import distribute_ig_stories, distribute_tg_stories

        if profile.platform == "instagram":
            sent_count = await distribute_ig_stories(
                bot=callback.bot,
                session=session,
                stories=stories,
                username=profile.ig_username,
                target_chat_id=callback.from_user.id,
                status_msg=status_msg
            )
        else:
            sent_count = await distribute_tg_stories(
                bot=callback.bot,
                session=session,
                stories=stories,
                username=profile.ig_username,
                target_chat_id=callback.from_user.id,
                status_msg=status_msg,
                peer_id=profile.ig_user_id
            )

        await status_msg.edit_text(
            f"✅ <b>@{profile.ig_username} {emoji}</b>: Barcha {sent_count} ta hikoyalar yuborildi!"
        )

    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {e}")
