import asyncio
import logging
import json
from datetime import datetime, timedelta, timezone

from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.utils.validators import extract_instagram_url, extract_instagram_username
from bot.services.instagram import ig_service
from bot.database.models import Download

logger = logging.getLogger(__name__)
router = Router(name="messages")

download_semaphore = asyncio.Semaphore(3)

from aiogram.exceptions import TelegramRetryAfter

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
        select(Download).where(Download.url == url).where(Download.file_id != None).limit(1)
    )
    cached_download = result.scalar_one_or_none()

    if cached_download and cached_download.file_id:
        logger.info(f"Cache hit for POST: {url}")
        try:
            if cached_download.media_type in ("video", "photo"):
                file_ids = [{"type": cached_download.media_type, "file_id": cached_download.file_id}]
            else:
                file_ids = json.loads(cached_download.file_id)
                
            await send_cached_items_individually(message, file_ids, caption="📥 Yuklab olindi (Keshdan)")
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
                file = BufferedInputFile(item["data"], filename=f"media.{'mp4' if item['type'] == 'video' else 'jpg'}")
                
                while True:
                    try:
                        if item["type"] == "video":
                            sent_msg = await message.answer_video(file, caption=caption)
                            sent_file_ids.append({"type": "video", "file_id": sent_msg.video.file_id})
                        else:
                            sent_msg = await message.answer_photo(file, caption=caption)
                            sent_file_ids.append({"type": "photo", "file_id": sent_msg.photo[-1].file_id})
                        
                        await asyncio.sleep(0.5)
                        break
                    except TelegramRetryAfter as e:
                        logger.warning(f"Flood control exceeded. Sleeping for {e.retry_after} seconds.")
                        await asyncio.sleep(e.retry_after + 1)

            if not sent_file_ids:
                await status_msg.edit_text("❌ Mediani yuklab olishni imkoni bo'lmadi.")
                return

            media_type = "carousel" if len(sent_file_ids) > 1 else sent_file_ids[0]["type"]
            cached_file_id = json.dumps(sent_file_ids) if len(sent_file_ids) > 1 else sent_file_ids[0]["file_id"]

            new_dl = Download(
                user_id=user_id, 
                platform="instagram", 
                media_type=media_type, 
                url=url, 
                file_id=cached_file_id
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
    
    time_threshold = datetime.now(timezone.utc) - timedelta(minutes=10)
    result = await session.execute(
        select(Download)
        .where(Download.url == f"story_{username}")
        .where(Download.file_id != None)
        .where(Download.downloaded_at >= time_threshold)
        .order_by(Download.downloaded_at.desc())
        .limit(1)
    )
    cached_story = result.scalar_one_or_none()

    if cached_story and cached_story.file_id:
        logger.info(f"Story cache hit for @{username}")
        try:
            file_ids = json.loads(cached_story.file_id)
            await send_cached_items_individually(message, file_ids, caption=f"📥 @{username} hikoyasi (Keshdan)")
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
                caption = f"📥 @{username} hikoyasi ({idx}/{total})" if total > 1 else f"📥 @{username} hikoyasi"
                file = BufferedInputFile(item["data"], filename=f"story.{'mp4' if item['type'] == 'video' else 'jpg'}")
                
                while True:
                    try:
                        if item["type"] == "video":
                            sent_msg = await message.answer_video(file, caption=caption)
                            sent_file_ids.append({"type": "video", "file_id": sent_msg.video.file_id})
                        else:
                            sent_msg = await message.answer_photo(file, caption=caption)
                            sent_file_ids.append({"type": "photo", "file_id": sent_msg.photo[-1].file_id})
                            
                        await asyncio.sleep(0.5)
                        break
                    except TelegramRetryAfter as e:
                        logger.warning(f"Flood control exceeded. Sleeping for {e.retry_after} seconds.")
                        await asyncio.sleep(e.retry_after + 1)
                    
            if not sent_file_ids:
                await status_msg.edit_text(f"❌ @{username} profilida so'nggi 24 soat ichida hikoyalar topilmadi yoki profil yopiq.")
                return
            
            new_dl = Download(
                user_id=user_id, 
                platform="instagram", 
                media_type="stories", 
                url=f"story_{username}", 
                file_id=json.dumps(sent_file_ids)
            )
            session.add(new_dl)
            await session.commit()
            
            await status_msg.delete()
        except Exception as e:
            logger.error(f"Error processing stories for {username}: {e}")
            await status_msg.edit_text("❌ Hikoyalarni yuklashda xatolik yuz berdi.")

@router.message(F.text)
async def process_text_message(message: Message, session: AsyncSession):
    text = message.text
    
    url = extract_instagram_url(text)
    if url:
        return await handle_post_download(message, session, url)
        
    username = extract_instagram_username(text)
    if username:
        return await handle_story_download(message, session, username)
