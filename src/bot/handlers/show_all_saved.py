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

router = Router(name="show_all_saved")


@router.message(Command("show_all_saved"))
async def show_all_saved_profiles(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    result = await session.execute(select(SavedProfile).where(SavedProfile.user_id == user_id))
    profiles = result.scalars().all()

    if not profiles:
        await message.answer("Sizda hech qanday saqlangan profil yo'q. /save orqali qo'shing.")
        return

    keyboard = []
    for p in profiles:
        emoji = "📸" if p.platform == "instagram" else "✈️"
        text = f"{emoji} @{p.ig_username}"
        keyboard.append([InlineKeyboardButton(text=text, callback_data=f"cache_prof_{p.id}")])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer(
        "🗄 <b>Arxivdagi profillar:</b>\n\nQaysi profilning kanalga saqlangan hikoyalarini ko'rmoqchisiz?",
        reply_markup=markup,
    )


@router.callback_query(F.data.startswith("cache_prof_"))
async def show_cached_stories(callback: CallbackQuery, session: AsyncSession):
    profile_id = int(callback.data.split("_")[2])

    result = await session.execute(select(SavedProfile).where(SavedProfile.id == profile_id))
    profile = result.scalar_one_or_none()

    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    # Fetch cached stories for this username and platform
    cache_res = await session.execute(
        select(StoryCache)
        .where(
            StoryCache.ig_username == profile.ig_username, StoryCache.platform == profile.platform
        )
        .order_by(StoryCache.downloaded_at.desc())
        .limit(50)  # Bitta xabarga juda ko'p button sig'masligi uchun limit
    )
    cached_stories = cache_res.scalars().all()

    if not cached_stories:
        await callback.answer("Bu profil uchun arxivda hikoyalar topilmadi.", show_alert=True)
        return

    keyboard = []
    # Button to download all
    keyboard.append(
        [
            InlineKeyboardButton(
                text="📥 Barchasini bitta olish", callback_data=f"dl_all_{profile_id}"
            )
        ]
    )

    # List individual stories
    for story in cached_stories:
        date_str = story.downloaded_at.strftime("%Y-%m-%d %H:%M")
        keyboard.append(
            [InlineKeyboardButton(text=f"📅 {date_str}", callback_data=f"dl_story_{story.id}")]
        )

    keyboard.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="show_all_saved_back")])
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    emoji = "📸" if profile.platform == "instagram" else "✈️"
    await callback.message.edit_text(
        f"🗄 <b>@{profile.ig_username} {emoji} arxiv hikoyalari:</b>\n\nJami: {len(cached_stories)} ta arxivlangan hikoya mavjud.",
        reply_markup=markup,
    )


@router.callback_query(F.data == "show_all_saved_back")
async def show_all_saved_back(callback: CallbackQuery, session: AsyncSession):
    import contextlib

    with contextlib.suppress(Exception):
        await callback.message.delete()

    # Soxta message obyekti yasab chaqiramiz
    message = callback.message
    message.from_user = callback.from_user
    await show_all_saved_profiles(message, session)


@router.callback_query(F.data.startswith("dl_story_"))
async def download_single_cached_story(callback: CallbackQuery, session: AsyncSession):
    story_id = int(callback.data.split("_")[2])

    res = await session.execute(select(StoryCache).where(StoryCache.id == story_id))
    story = res.scalar_one_or_none()

    if not story or not config.storage_channel_id:
        await callback.answer("Hikoya topilmadi yoki kanal sozlanmagan.", show_alert=True)
        return

    await callback.answer("Yuborilmoqda...")
    try:
        await callback.bot.copy_message(
            chat_id=callback.from_user.id,
            from_chat_id=config.storage_channel_id,
            message_id=story.telegram_msg_id,
        )
    except Exception:
        await callback.message.answer(
            "❌ Xatolik: Hikoyani kanal orqali yuborish imkonsiz (Ehtimol o'chirilgan)."
        )


@router.callback_query(F.data.startswith("dl_all_"))
async def download_all_cached_stories(callback: CallbackQuery, session: AsyncSession):
    profile_id = int(callback.data.split("_")[2])

    res = await session.execute(select(SavedProfile).where(SavedProfile.id == profile_id))
    profile = res.scalar_one_or_none()

    if not profile:
        await callback.answer("Profil topilmadi.", show_alert=True)
        return

    cache_res = await session.execute(
        select(StoryCache)
        .where(
            StoryCache.ig_username == profile.ig_username, StoryCache.platform == profile.platform
        )
        .order_by(StoryCache.downloaded_at.asc())  # Xronologik ketma ketlikda yuborish uchun asc
        .limit(50)
    )
    cached_stories = cache_res.scalars().all()

    if not cached_stories or not config.storage_channel_id:
        await callback.answer("Hikoyalar topilmadi yoki kanal sozlanmagan.", show_alert=True)
        return

    await callback.answer("Barchasi yuborilmoqda, biroz kuting...")

    sent = 0
    for story in cached_stories:
        try:
            await callback.bot.copy_message(
                chat_id=callback.from_user.id,
                from_chat_id=config.storage_channel_id,
                message_id=story.telegram_msg_id,
            )
            sent += 1
        except Exception:
            pass

    await callback.message.answer(f"✅ Barcha {sent} ta hikoya arxivdan muvaffaqiyatli yuborildi!")
