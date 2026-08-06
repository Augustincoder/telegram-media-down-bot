from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.config import config
from bot.database.models import InstagramPairing
from bot.services.pairing_cache import pairing_cache

router = Router(name="pairing")


@router.message(Command("link_instagram"))
@router.message(Command("link_ig"))
@router.message(F.text == "🔗 Akkaunt ulash")
async def link_instagram_handler(message: Message, session: AsyncSession):
    user_id = message.from_user.id

    # 1. Avval allaqachon bog'langanligini tekshiramiz
    result = await session.execute(
        select(InstagramPairing).where(
            InstagramPairing.user_id == user_id, InstagramPairing.is_active == True
        )
    )
    existing_pairings = result.scalars().all()

    count_text = ""
    if existing_pairings:
        count_text = f"✅ <b>Holat:</b> Sizning Telegramingizga hozirda {len(existing_pairings)} ta Instagram profil ulangan.\nYana akkaunt ulash uchun pastdagi ko'rsatmani bajaring.\n\n"

    # 2. Yangi kod generatsiya qilamiz
    code = pairing_cache.generate_code(user_id)

    # 3. Yo'riqnoma yuboramiz
    ig_username = config.instagram_username or "rasmiy_bot_profilimiz"
    text = (
        "🔗 <b>Instagram Akkauntni Bog'lash (Pairing)</b>\n\n"
        f"{count_text}"
        "Do'stlaringiz sizga Direct orqali yuborgan yoki ulashgan (forward qilingan) Reels/Video larni yuklab olish uchun akkauntingizni bog'lashingiz kerak.\n\n"
        f"<b>Qanday qilinadi?</b>\n"
        f"1. Instagram'ga kiring va <code>{ig_username}</code> profiliga (qidiruv orqali topib) xabar (Direct Message) yozing.\n"
        f"2. Xabar matnida faqat quyidagi 6 xonali kodni yuboring:\n\n"
        f"<code>{code}</code>\n\n"
        "⏳ <i>Kod 10 daqiqa davomida o'z kuchini saqlaydi. Yuborganingizdan so'ng biroz kuting.</i>\n\n"
        "Ulangan akkauntlarni ko'rish va uzish uchun /linked tugmasini bosing."
    )

    await message.answer(text)


@router.message(Command("linked"))
async def linked_accounts_handler(message: Message, session: AsyncSession):
    user_id = message.from_user.id

    result = await session.execute(
        select(InstagramPairing).where(
            InstagramPairing.user_id == user_id, InstagramPairing.is_active == True
        )
    )
    pairings = result.scalars().all()

    if not pairings:
        await message.answer(
            "Sizda bog'langan Instagram akkauntlar yo'q. Ulanish uchun /link_instagram tugmasini bosing."
        )
        return

    text = "🔗 <b>Ulangan Instagram akkauntlaringiz:</b>\n\n"
    for idx, p in enumerate(pairings, start=1):
        display_name = (
            f"@{p.instagram_username}"
            if p.instagram_username
            else f"ID: {p.instagram_user_id}"
        )
        text += f"{idx}. <b>{display_name}</b>\n"

    text += "\n<i>Barcha ulanishlarni uzib tashlash uchun /unlink_all tugmasini bosing. Yoki bittasini uzish uchun /unlink_instagram @username (yoki ID) formatida yuboring.</i>"
    await message.answer(text)


import random
import string

UNLINK_CONFIRMATIONS = {}

@router.message(Command("unlink_all"))
async def unlink_all_handler(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    result = await session.execute(
        select(InstagramPairing).where(InstagramPairing.user_id == user_id)
    )
    pairings = result.scalars().all()

    if not pairings:
        await message.answer("Sizda bog'langan Instagram akkaunt topilmadi.")
        return

    random_word = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    UNLINK_CONFIRMATIONS[user_id] = random_word

    await message.answer(
        "⚠️ <b>DIQQAT!</b> Siz barcha ulangan Instagram akkauntlarini uzmoqchisiz.\n\n"
        "Buni tasdiqlash uchun quyidagi tasodifiy so'zni nusxalab (ustiga bosib) menga yuboring:\n\n"
        f"<code>{random_word}</code>"
    )

@router.message(lambda msg: msg.from_user.id in UNLINK_CONFIRMATIONS and msg.text and msg.text.strip() == UNLINK_CONFIRMATIONS[msg.from_user.id])
async def confirm_unlink_all_handler(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    
    result = await session.execute(
        select(InstagramPairing).where(InstagramPairing.user_id == user_id)
    )
    pairings = result.scalars().all()

    for p in pairings:
        await session.delete(p)
    await session.commit()
    
    if user_id in UNLINK_CONFIRMATIONS:
        del UNLINK_CONFIRMATIONS[user_id]

    await message.answer(
        "🗑 Barcha Instagram profillar bilan bog'lanish muvaffaqiyatli uzildi!"
    )


@router.message(Command("unlink_instagram"))
async def unlink_instagram_handler(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    args = message.text.split()

    if len(args) < 2:
        await message.answer(
            "❌ Qaysi akkauntni uzishni ko'rsatmadingiz. Iltimos, /linked orqali profilni topib, <code>/unlink_instagram @username</code> shaklida yuboring."
        )
        return

    target_ig = args[1].replace("@", "").strip()

    result = await session.execute(
        select(InstagramPairing).where(
            InstagramPairing.user_id == user_id,
            (InstagramPairing.instagram_user_id == target_ig)
            | (InstagramPairing.instagram_username == target_ig),
        )
    )
    existing_pairing = result.scalar_one_or_none()

    if not existing_pairing:
        await message.answer(f"❌ <b>{target_ig}</b> ga bog'langan akkaunt topilmadi.")
        return

    deleted_target = (
        existing_pairing.instagram_username or existing_pairing.instagram_user_id
    )
    await session.delete(existing_pairing)
    await session.commit()

    await message.answer(
        f"🗑 <b>{deleted_target}</b> Instagram profilingiz bilan bog'lanish muvaffaqiyatli uzildi!"
    )
