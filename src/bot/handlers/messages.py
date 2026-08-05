import asyncio
import contextlib
import json
import logging
import os
from datetime import UTC, datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import BufferedInputFile, CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.database.models import Download
from bot.services.instagram import ig_service
from bot.services.telegram_userbot import userbot_service
from bot.utils.validators import (
    extract_instagram_url,
    extract_instagram_username,
    extract_simple_username,
    extract_telegram_story_info,
)

logger = logging.getLogger(__name__)
router = Router(name="messages")

download_semaphore = asyncio.Semaphore(3)


async def send_cached_items_individually(message: Message, file_ids: list[dict], caption_base: str):
    """Keshdagi fayllarni guruhlamasdan, ketma-ket alohida xabar qilib yuboradi."""
    total = len(file_ids)
    for idx, item in enumerate(file_ids, start=1):
        caption = f"{caption_base} ({idx}/{total})" if total > 1 else caption_base
        while True:
            try:
                if item["type"] == "video":
                    await message.answer_video(item["file_id"], caption=caption)
                else:
                    await message.answer_photo(item["file_id"], caption=caption)

                # Telegram limitlariga tushib qolmaslik uchun kichik tanaffus
                await asyncio.sleep(0.5)
                break
            except TelegramRetryAfter as e:
                logger.warning(f"Flood control exceeded. Sleeping for {e.retry_after} seconds.")
                await asyncio.sleep(e.retry_after + 1)


async def handle_post_download(message: Message, session: AsyncSession, url: str):
    """Reels, Post va Karusellarni keshlash va oqim (stream) ko'rinishida yuklash"""
    user_id = message.from_user.id

    result = await session.execute(
        select(Download).where(Download.url == url).where(Download.file_id is not None).limit(1)
    )
    cached_download = result.scalar_one_or_none()

    if cached_download and cached_download.file_id:
        logger.info(f"Cache hit for POST: {url}")
        try:
            if cached_download.media_type in ("video", "photo"):
                file_ids = [
                    {"type": cached_download.media_type, "file_id": cached_download.file_id}
                ]
            else:
                file_ids = json.loads(cached_download.file_id)

            await send_cached_items_individually(
                message, file_ids, caption_base="📥 Yuklab olindi (Keshdan)"
            )
            return
        except Exception as e:
            logger.error(f"Post keshni o'qishda xatolik: {e}")

    status_msg = await message.answer("⚡ Media tekshirilmoqda, yuklash boshlanadi...")
    async with download_semaphore:
        try:
            sent_file_ids = []

            # Oqim qabul qilish va kelgan onida darhol yuborish
            async for item in ig_service.stream_instagram_media(url):
                total = item.get("total", 1)
                idx = item.get("index", 1)
                caption = f"📥 Yuklab olindi ({idx}/{total})" if total > 1 else "📥 Yuklab olindi"
                file = BufferedInputFile(
                    item["data"], filename=f"media.{'mp4' if item['type'] == 'video' else 'jpg'}"
                )

                while True:
                    try:
                        if item["type"] == "video":
                            sent_msg = await message.answer_video(file, caption=caption)
                            sent_file_ids.append(
                                {"type": "video", "file_id": sent_msg.video.file_id}
                            )
                        else:
                            sent_msg = await message.answer_photo(file, caption=caption)
                            sent_file_ids.append(
                                {"type": "photo", "file_id": sent_msg.photo[-1].file_id}
                            )

                        await asyncio.sleep(0.5)
                        break
                    except TelegramRetryAfter as e:
                        logger.warning(
                            f"Flood control exceeded. Sleeping for {e.retry_after} seconds."
                        )
                        await asyncio.sleep(e.retry_after + 1)

            if not sent_file_ids:
                await status_msg.edit_text("❌ Mediani yuklab olishni imkoni bo'lmadi.")
                return

            media_type = "carousel" if len(sent_file_ids) > 1 else sent_file_ids[0]["type"]
            cached_file_id = (
                json.dumps(sent_file_ids) if len(sent_file_ids) > 1 else sent_file_ids[0]["file_id"]
            )

            new_dl = Download(
                user_id=user_id,
                platform="instagram",
                media_type=media_type,
                url=url,
                file_id=cached_file_id,
            )
            session.add(new_dl)
            await session.commit()

            await status_msg.delete()
        except ValueError as e:
            logger.error(f"ValueError processing {url}: {e}")
            await status_msg.edit_text(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            await status_msg.edit_text("❌ Tizimda kutilmagan xatolik yuz berdi.")


async def handle_story_download(message: Message, session: AsyncSession, username: str):
    """Hikoyalarni (Stories) keshlash va oqim (stream) sifatida ketma-ket yuborish"""
    user_id = message.from_user.id

    time_threshold = datetime.now(UTC) - timedelta(minutes=10)
    result = await session.execute(
        select(Download)
        .where(Download.url == f"story_{username}")
        .where(Download.file_id is not None)
        .where(Download.downloaded_at >= time_threshold)
        .order_by(Download.downloaded_at.desc())
        .limit(1)
    )
    cached_story = result.scalar_one_or_none()

    if cached_story and cached_story.file_id:
        logger.info(f"Story cache hit for @{username}")
        try:
            file_ids = json.loads(cached_story.file_id)
            await send_cached_items_individually(
                message, file_ids, caption_base=f"📥 @{username} hikoyasi (Keshdan)"
            )
            return
        except Exception as e:
            logger.error(f"Story keshini o'qishda xatolik: {e}")

    status_msg = await message.answer(f"⚡ @{username} profilidan hikoyalar tortilmoqda...")
    async with download_semaphore:
        try:
            sent_file_ids = []

            async for item in ig_service.stream_user_stories(username):
                total = item.get("total", 1)
                idx = item.get("index", 1)
                caption = (
                    f"📥 @{username} hikoyasi ({idx}/{total})"
                    if total > 1
                    else f"📥 @{username} hikoyasi"
                )
                file = BufferedInputFile(
                    item["data"], filename=f"story.{'mp4' if item['type'] == 'video' else 'jpg'}"
                )

                while True:
                    try:
                        if item["type"] == "video":
                            sent_msg = await message.answer_video(file, caption=caption)
                            sent_file_ids.append(
                                {"type": "video", "file_id": sent_msg.video.file_id}
                            )
                        else:
                            sent_msg = await message.answer_photo(file, caption=caption)
                            sent_file_ids.append(
                                {"type": "photo", "file_id": sent_msg.photo[-1].file_id}
                            )

                        await asyncio.sleep(0.5)
                        break
                    except TelegramRetryAfter as e:
                        logger.warning(
                            f"Flood control exceeded. Sleeping for {e.retry_after} seconds."
                        )
                        await asyncio.sleep(e.retry_after + 1)

            if not sent_file_ids:
                await status_msg.edit_text(
                    f"❌ @{username} profilida so'nggi 24 soat ichida hikoyalar topilmadi yoki profil yopiq."
                )
                return

            new_dl = Download(
                user_id=user_id,
                platform="instagram",
                media_type="stories",
                url=f"story_{username}",
                file_id=json.dumps(sent_file_ids),
            )
            session.add(new_dl)
            await session.commit()

            await status_msg.delete()
        except Exception as e:
            logger.error(f"Error processing stories for {username}: {e}")
            await status_msg.edit_text("❌ Hikoyalarni yuklashda xatolik yuz berdi.")


async def handle_telegram_story(message: Message, session: AsyncSession, peer: str, story_id: int):
    """Telegram hikoyasini Userbot orqali yuklash"""
    if not userbot_service.is_connected:
        await message.answer("❌ Telegram Userbot ulanmagan. Iltimos, adminlarga murojaat qiling.")
        return

    status_msg = await message.answer("⚡ Telegram hikoyasi tortilmoqda...")

    import os

    file_path = f"downloads/tg_story_{peer}_{story_id}.mp4"
    os.makedirs("downloads", exist_ok=True)

    try:
        downloaded = await userbot_service.download_story(peer, story_id, file_path)
        if not downloaded:
            await status_msg.edit_text(
                "❌ Hikoya topilmadi yoki men uni ko'ra olmayman (yopiq profil)."
            )
            return

        from aiogram.types import FSInputFile

        media = FSInputFile(downloaded)

        # Fajl kengaytmasiga qarab video yoki rasm sifatida yuborish
        if downloaded.endswith(".mp4"):
            await message.answer_video(media, caption="📥 Telegram hikoyasi")
        else:
            await message.answer_photo(media, caption="📥 Telegram hikoyasi")

        await status_msg.delete()
        os.remove(downloaded)
    except Exception as e:
        logger.error(f"Telegram hikoya xatosi: {e}")
        await status_msg.edit_text("❌ Telegram hikoyasini yuklashda kutilmagan xato yuz berdi.")


async def handle_all_telegram_stories(message: Message, peer: str):
    """Barcha Telegram hikoyalarini yuklash"""
    if not userbot_service.is_connected:
        await message.answer("❌ Telegram Userbot ulanmagan. Iltimos, adminlarga murojaat qiling.")
        return

    status_msg = await message.answer(f"⚡ @{peer} ning barcha Telegram hikoyalari qidirilmoqda...")

    os.makedirs("downloads", exist_ok=True)

    try:
        found = False
        async for file in userbot_service.stream_all_stories(peer, "downloads"):
            found = True
            media = FSInputFile(file)

            while True:
                try:
                    if file.endswith(".mp4"):
                        await message.answer_video(media, caption=f"📥 @{peer} Telegram hikoyasi")
                    else:
                        await message.answer_photo(media, caption=f"📥 @{peer} Telegram hikoyasi")
                    await asyncio.sleep(0.5)
                    break
                except TelegramRetryAfter as e:
                    logger.warning(f"Flood control exceeded. Sleeping for {e.retry_after} seconds.")
                    await asyncio.sleep(e.retry_after + 1)

            # Jo'natib bo'lingach darhol o'chiramiz
            with contextlib.suppress(OSError):
                os.remove(file)

        if not found:
            await status_msg.edit_text(
                f"❌ @{peer} da aktiv hikoyalar topilmadi yoki ko'ra olmayman."
            )
            return

        await status_msg.delete()
    except Exception as e:
        logger.error(f"Barcha Telegram hikoyalarini yuklashda xato: {e}")
        await status_msg.edit_text("❌ Hikoyalarni yuklashda kutilmagan xato yuz berdi.")


@router.callback_query(F.data.startswith("set_"))
async def process_settings(callback: CallbackQuery):
    await callback.answer("Ushbu funksiya ishlab chiqilmoqda! 🛠", show_alert=True)


@router.callback_query(F.data.startswith("down_ig_"))
async def process_down_ig(callback: CallbackQuery, session: AsyncSession):
    username = callback.data.split("down_ig_")[1]
    await callback.message.delete()
    await handle_story_download(callback.message, session, username)


@router.callback_query(F.data.startswith("down_tg_"))
async def process_down_tg(callback: CallbackQuery):
    peer = callback.data.split("down_tg_")[1]
    await callback.message.delete()
    await handle_all_telegram_stories(callback.message, peer)


@router.message(F.text)
async def process_text_message(message: Message, session: AsyncSession):
    text = message.text

    # Menyu tugmalarini ushlash
    if text == "📥 Yuklab olish":
        return await message.answer(
            "Men tayyorman! 😎 Shunchaki Instagram yoki Telegramdan havola/username yuboring."
        )

    if text == "💾 Saqlangan profillar":
        from bot.handlers.saved import saved_profiles_handler

        return await saved_profiles_handler(message, session)

    if text == "🔗 Akkaunt ulash":
        from bot.handlers.pairing import link_instagram_handler

        return await link_instagram_handler(message, session)

    if text == "⚙️ Sozlamalar":
        builder = InlineKeyboardBuilder()
        builder.button(text="🇺🇿 Til (O'zbek)", callback_data="set_lang")
        builder.button(text="🔔 Bildirishnomalar: Yoqilgan", callback_data="set_notif")
        builder.adjust(1)
        return await message.answer(
            "⚙️ <b>Sozlamalar paneli</b>\n\n"
            "O'zingizga mos ravishda botni sozlang (bu funksiyalar tez orada to'liq ishga tushadi):",
            reply_markup=builder.as_markup(),
        )

    if text == "ℹ️ Yordam / Qoidalar":
        from bot.handlers.commands import cmd_help

        return await cmd_help(message)

    tg_story = extract_telegram_story_info(text)
    if tg_story:
        peer, story_id = tg_story
        return await handle_telegram_story(message, session, peer, story_id)

    url = extract_instagram_url(text)
    if url:
        return await handle_post_download(message, session, url)

    username = extract_instagram_username(text)
    if username:
        return await handle_story_download(message, session, username)

    simple = extract_simple_username(text)
    if simple:
        builder = InlineKeyboardBuilder()
        builder.button(text="📸 Instagram", callback_data=f"down_ig_{simple}")
        builder.button(text="✈️ Telegram", callback_data=f"down_tg_{simple}")
        builder.adjust(2)

        await message.answer(
            "Barcha hikoyalarni yuklash uchun ijtimoiy tarmoqni tanlang:",
            reply_markup=builder.as_markup(),
        )
