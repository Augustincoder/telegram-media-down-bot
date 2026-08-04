from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.database.models import InstagramPairing
from bot.services.pairing_cache import pairing_cache
from bot.config import config

router = Router(name="pairing")

@router.message(Command("link_instagram"))
async def link_instagram_handler(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    
    # 1. Avval allaqachon bog'langanligini tekshiramiz
    result = await session.execute(
        select(InstagramPairing).where(InstagramPairing.user_id == user_id).limit(1)
    )
    existing_pairing = result.scalar_one_or_none()
    
    if existing_pairing and existing_pairing.is_active:
        await message.answer(
            f"✅ Sizning Telegram akkauntingiz allaqachon Instagram profil (ID: {existing_pairing.instagram_user_id}) bilan bog'langan!\n"
            "Videolarni (Direct uzatma orqali) tortish uchun IG akkauntimizga yuborishingiz mumkin."
        )
        return

    # 2. Yangi kod generatsiya qilamiz
    code = pairing_cache.generate_code(user_id)
    
    # 3. Yo'riqnoma yuboramiz
    ig_username = config.instagram_username or "rasmiy_bot_profilimiz"
    text = (
        "🔗 <b>Instagram Akkauntni Bog'lash (Pairing)</b>\n\n"
        "Do'stlaringiz sizga Direct orqali yuborgan yoki ulashgan (forward qilingan) Reels/Video larni yuklab olish uchun akkauntingizni bog'lashingiz kerak.\n\n"
        f"<b>Qanday qilinadi?</b>\n"
        f"1. Instagram'ga kiring va <code>{ig_username}</code> profiliga (qidiruv orqali topib) xabar (Direct Message) yozing.\n"
        f"2. Xabar matnida faqat quyidagi 6 xonali kodni yuboring:\n\n"
        f"<code>{code}</code>\n\n"
        "⏳ <i>Kod 10 daqiqa davomida o'z kuchini saqlaydi. Yuborganingizdan so'ng biroz kuting.</i>"
    )
    
    await message.answer(text)
