import asyncio
import logging
import json
from datetime import datetime, timedelta, timezone

from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.utils.validators import extract_instagram_url, extract_instagram_username
from bot.services.instagram import ig_service
from bot.database.models import Download
from bot.handlers.media_helpers import send_downloaded_media, send_cached_media

logger = logging.getLogger(__name__)
router = Router(name="messages")

download_semaphore = asyncio.Semaphore(3)

async def handle_post_download(message: Message, session: AsyncSession, url: str):
    """Reels, Post va Karusellarni keshlash va yuklash logikasi"""
    user_id = message.from_user.id
    
    # 1. Keshni tekshirish
    result = await session.execute(
        select(Download).where(Download.url == url).where(Download.file_id != None).limit(1)
    )
    cached_download = result.scalar_one_or_none()

    if cached_download and cached_download.file_id:
        logger.info(f"Cache hit for POST: {url}")
        try:
            # Fayllar strukturasi qanday bo'lishidan qat'i nazar, JSON formatiga keltiramiz
            if cached_download.media_type in ("video", "photo"):
                file_ids = [{"type": cached_download.media_type, "file_id": cached_download.file_id}]
            else:
                file_ids = json.loads(cached_download.file_id)
                
            await send_cached_media(message, file_ids, caption="📥 Yuklab olindi (Keshdan)")
            return
        except Exception as e:
            logger.error(f"Post keshni o'qishda xatolik: {e}")

    # 2. Yangi yuklash jarayoni
    status_msg = await message.answer("⚡ Media yuklanmoqda...")
    async with download_semaphore:
        try:
            media_items = await ig_service.get_instagram_media(url)
            if not media_items:
                await status_msg.edit_text("❌ Mediani yuklab olishni imkoni bo'lmadi.")
                return

            # Helper orqali media fayllarini Telegramga yuborish
            sent_file_ids = await send_downloaded_media(message, media_items, caption="📥 Yuklab olindi")
            
            # 3. Natijalarni keshga yozish
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
    """Hikoyalarni (Stories) keshlash va yuklash logikasi"""
    user_id = message.from_user.id
    
    # 1. Hikoyalar uchun maxsus "10 daqiqalik" keshni tekshirish
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
            await send_cached_media(message, file_ids, caption=f"📥 @{username} hikoyalari (Keshdan)")
            return
        except Exception as e:
            logger.error(f"Story keshini o'qishda xatolik: {e}")

    # 2. Yangi hikoyalarni yuklash
    status_msg = await message.answer(f"⚡ @{username} profili tahlil qilinmoqda...")
    async with download_semaphore:
        try:
            stories = await ig_service.get_user_stories(username)
            if not stories:
                await status_msg.edit_text(f"❌ @{username} profilida so'nggi 24 soat ichida hikoyalar topilmadi yoki profil yopiq (Private).")
                return

            await status_msg.edit_text(f"⚡ @{username} profilidan jami {len(stories)} ta hikoya topildi, yuklanmoqda...")
            
            # Helper orqali barcha hikoyalarni Telegramga yuborish
            sent_file_ids = await send_downloaded_media(message, stories, caption=f"📥 @{username} hikoyasi")
            
            # 3. Hikoyalar keshini JSON array sifatida bitta qatorda saqlash
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
    """Barcha matnli xabarlarni tutib olib, tegishli funktsiyaga yo'naltiruvchi (Router) vazifasini bajaradi."""
    text = message.text
    
    url = extract_instagram_url(text)
    if url:
        return await handle_post_download(message, session, url)
        
    username = extract_instagram_username(text)
    if username:
        return await handle_story_download(message, session, username)
