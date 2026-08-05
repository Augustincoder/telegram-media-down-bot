import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.config import config
from bot.database.models import Download, User

logger = logging.getLogger(__name__)
router = Router(name="commands")


def get_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📥 Yuklab olish"),
                KeyboardButton(text="💾 Saqlangan profillar"),
            ],
            [
                KeyboardButton(text="🔗 Akkaunt ulash"),
                KeyboardButton(text="⚙️ Sozlamalar"),
            ],
            [KeyboardButton(text="ℹ️ Yordam / Qoidalar")],
        ],
        resize_keyboard=True,
        persistent=True,
    )


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name

    # Check if user exists
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(id=user_id, username=username, full_name=full_name)
        session.add(user)
        await session.commit()
        logger.info(f"New user registered: {full_name} ({user_id})")

    await message.answer(
        f"Assalomu alaykum, {full_name}!\n\n"
        "Menga quyidagilardan birini yuboring:\n"
        "🔗 <b>Instagram Reels/Post/Story havolasi</b>\n"
        "🔗 <b>Telegram Story havolasi</b>\n"
        "👤 Yoki shunchaki <b>username</b> (masalan: <code>durov</code>)\n\n"
        "Men sizga uni darhol videokorinishida yuklab beraman!",
        reply_markup=get_main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "📖 <b>Botdan foydalanish qoidalari:</b>\n\n"
        "1️⃣ Ochiq profillardagi Reels/Post havolasini yuboring, men uni tortib beraman.\n"
        "2️⃣ Yopiq profillardan tortish uchun: <b>🔗 Akkaunt ulash</b> menyusi orqali profilingizni botga ulang.\n"
        "3️⃣ Telegram hikoyalari (Story) yoki Instagram hikoyalarini yuklash uchun shunchaki o'sha insonning "
        "<b>username</b> (masalan: @durov) ini yuboring.\n\n"
        "Sevimlilarni saqlab qolish uchun /save [username] komandasidan foydalaning!"
    )
    await message.answer(text, reply_markup=get_main_menu())


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession):
    if message.from_user.id not in config.admin_ids:
        return

    users_count = await session.scalar(select(func.count(User.id)))
    downloads_count = await session.scalar(select(func.count(Download.id)))

    # Bugungi yuklamalar
    from datetime import UTC, datetime

    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_downloads = await session.scalar(
        select(func.count(Download.id)).where(Download.downloaded_at >= today)
    )

    text = (
        "📊 <b>Bot Statistikasi</b>\n\n"
        f"👥 Umumiy foydalanuvchilar: <b>{users_count}</b> ta\n"
        f"📥 Umumiy yuklamalar: <b>{downloads_count}</b> ta\n"
        f"⚡ Bugungi yuklamalar: <b>{today_downloads}</b> ta\n"
    )
    await message.answer(text)
