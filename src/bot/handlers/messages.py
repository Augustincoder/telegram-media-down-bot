import asyncio
import logging
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.utils.validators import extract_instagram_url
from bot.services.instagram import ig_service
from bot.database.models import Download

logger = logging.getLogger(__name__)
router = Router(name="messages")

# Max 3 concurrent downloads to avoid overwhelming the VPS
download_semaphore = asyncio.Semaphore(3)

# Define downloads path
DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)


@router.message(F.text)
async def process_text_message(message: Message, session: AsyncSession):
    text = message.text
    url = extract_instagram_url(text)

    if not url:
        return # Ignore non-instagram messages, or you could reply: await message.answer("Iltimos, faqat Instagram linkini yuboring.")

    user_id = message.from_user.id
    
    # Check cache in DB
    result = await session.execute(
        select(Download).where(Download.url == url).where(Download.file_id != None).limit(1)
    )
    cached_download = result.scalar_one_or_none()

    if cached_download and cached_download.file_id:
        logger.info(f"Cache hit for {url}")
        # Send from Telegram cache directly (fast)
        await message.answer_video(cached_download.file_id)
        
        # Log this download for the current user too
        new_dl = Download(user_id=user_id, platform="instagram", media_type="reels", url=url, file_id=cached_download.file_id)
        session.add(new_dl)
        await session.commit()
        return

    # Not cached, need to download
    status_msg = await message.answer("⏳ Video yuklanmoqda, iltimos kuting...")
    
    async with download_semaphore:
        try:
            file_path = await ig_service.download_reel(url, folder=DOWNLOADS_DIR)
            
            if not file_path or not file_path.exists():
                await status_msg.edit_text("❌ Videoni yuklab olishni imkoni bo'lmadi (Yopiq profil bo'lishi mumkin yoki hajmi juda katta).")
                return

            # Send video to Telegram
            video = FSInputFile(file_path)
            sent_msg = await message.answer_video(
                video, 
                caption="📥 @SizningBotingiz orqali yuklab olindi"
            )
            
            # Save to DB for caching
            new_dl = Download(
                user_id=user_id, 
                platform="instagram", 
                media_type="reels", 
                url=url, 
                file_id=sent_msg.video.file_id
            )
            session.add(new_dl)
            await session.commit()
            
            # Delete temporary file
            file_path.unlink()
            await status_msg.delete()
            
        except Exception as e:
            logger.error(f"Error processing reel {url}: {e}")
            await status_msg.edit_text("❌ Tizimda xatolik yuz berdi. Iltimos keyinroq qayta urinib ko'ring.")
            # Ensure cleanup if exists
            if 'file_path' in locals() and file_path and file_path.exists():
                file_path.unlink()
