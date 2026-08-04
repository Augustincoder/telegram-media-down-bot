import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.utils.validators import extract_instagram_url
from bot.services.instagram import ig_service
from bot.database.models import Download

logger = logging.getLogger(__name__)
router = Router(name="messages")

# Max 3 concurrent downloads
download_semaphore = asyncio.Semaphore(3)

@router.message(F.text)
async def process_text_message(message: Message, session: AsyncSession):
    text = message.text
    url = extract_instagram_url(text)

    if not url:
        return

    user_id = message.from_user.id
    
    # Check cache in DB (Juda tezkor javob uchun)
    result = await session.execute(
        select(Download).where(Download.url == url).where(Download.file_id != None).limit(1)
    )
    cached_download = result.scalar_one_or_none()

    if cached_download and cached_download.file_id:
        logger.info(f"Cache hit for {url}")
        # Send from Telegram cache directly (Instant)
        await message.answer_video(cached_download.file_id)
        
        # Log this download
        new_dl = Download(user_id=user_id, platform="instagram", media_type="reels", url=url, file_id=cached_download.file_id)
        session.add(new_dl)
        await session.commit()
        return

    # Yuklash boshlandi
    status_msg = await message.answer("⚡ Video yuklanmoqda...")
    
    async with download_semaphore:
        try:
            # Faylni diskka yozmaymiz, RAMda baytlarni olamiz
            video_bytes = await ig_service.download_reel_bytes(url)
            
            if not video_bytes:
                await status_msg.edit_text("❌ Videoni yuklab olishni imkoni bo'lmadi (Yopiq profil yoki hajm juda katta).")
                return

            # Baytlardan Telegram'ga videoni uzatamiz
            video = BufferedInputFile(video_bytes, filename="reels.mp4")
            sent_msg = await message.answer_video(
                video, 
                caption="📥 Yuklab olindi"
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
            
            await status_msg.delete()
            
        except ValueError as e:
            logger.error(f"ValueError processing {url}: {e}")
            await status_msg.edit_text(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"Error processing reel {url}: {e}")
            await status_msg.edit_text("❌ Tizimda xatolik yuz berdi. Iltimos keyinroq qayta urinib ko'ring.")
