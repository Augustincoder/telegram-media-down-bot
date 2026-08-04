import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.database.models import User

logger = logging.getLogger(__name__)
router = Router(name="commands")

@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name

    # Check if user exists
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=user_id,
            username=username,
            full_name=full_name
        )
        session.add(user)
        await session.commit()
        logger.info(f"New user registered: {full_name} ({user_id})")
    
    await message.answer(
        f"Assalomu alaykum, {full_name}!\n\n"
        "Menga Instagram Reels yoki Post linkini yuboring va men sizga uni videokorinisihda yuklab beraman!"
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Botdan foydalanish:\n\n"
        "1. Instagramdan Reels yoki Post havolasini nuxsalab oling.\n"
        "2. Shu chatga yuboring.\n"
        "3. Biroz kuting va videoni qabul qiling.\n\n"
        "Hozircha faqat ochiq (public) profillardagi videolarni yuklash imkoni mavjud."
    )
