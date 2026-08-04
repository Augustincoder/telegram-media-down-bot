import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.utils.media_group import MediaGroupBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.utils.validators import extract_instagram_url
from bot.services.instagram import ig_service
from bot.database.models import Download

logger = logging.getLogger(__name__)
router = Router(name="messages")

download_semaphore = asyncio.Semaphore(3)

@router.message(F.text)
async def process_text_message(message: Message, session: AsyncSession):
    text = message.text
    url = extract_instagram_url(text)

    if not url:
        return

    user_id = message.from_user.id
    
    # Kesh tekshiruvi (Hozircha faqat yakka rasm/videolar uchun to'liq ishlaydi)
    result = await session.execute(
        select(Download).where(Download.url == url).where(Download.file_id != None).limit(1)
    )
    cached_download = result.scalar_one_or_none()

    if cached_download and cached_download.file_id:
        logger.info(f"Cache hit for {url}")
        if cached_download.media_type == "video":
            await message.answer_video(cached_download.file_id)
        elif cached_download.media_type == "photo":
            await message.answer_photo(cached_download.file_id)
        return

    status_msg = await message.answer("⚡ Media yuklanmoqda...")
    
    async with download_semaphore:
        try:
            # Karusel yoki Yagona media yuklash
            media_items = await ig_service.get_instagram_media(url)
            
            if not media_items:
                await status_msg.edit_text("❌ Mediani yuklab olishni imkoni bo'lmadi.")
                return

            # Agar faqat 1 ta rasm/video bo'lsa
            if len(media_items) == 1:
                item = media_items[0]
                file = BufferedInputFile(item["data"], filename=f"file.{'mp4' if item['type'] == 'video' else 'jpg'}")
                
                if item["type"] == "video":
                    sent_msg = await message.answer_video(file, caption="📥 Yuklab olindi")
                    file_id = sent_msg.video.file_id
                else:
                    sent_msg = await message.answer_photo(file, caption="📥 Yuklab olindi")
                    file_id = sent_msg.photo[-1].file_id
                    
                # Baza keshiga saqlash
                new_dl = Download(user_id=user_id, platform="instagram", media_type=item["type"], url=url, file_id=file_id)
                session.add(new_dl)
                await session.commit()
                
            # Agar karusel (albom) bo'lsa
            else:
                media_group = MediaGroupBuilder(caption="📥 Karusel yuklab olindi")
                for idx, item in enumerate(media_items):
                    file = BufferedInputFile(item["data"], filename=f"media_{idx}.{'mp4' if item['type']=='video' else 'jpg'}")
                    if item["type"] == "video":
                        media_group.add_video(media=file)
                    else:
                        media_group.add_photo(media=file)
                
                await message.answer_media_group(media_group.build())
                
                # Karusel uchun bazaga yozamiz, lekin file_id qoldirmaymiz, sababi kesh tizimi MediaGroup uchun alohida jadval/JSON kutar ekan
                new_dl = Download(user_id=user_id, platform="instagram", media_type="carousel", url=url)
                session.add(new_dl)
                await session.commit()
            
            await status_msg.delete()
            
        except ValueError as e:
            logger.error(f"ValueError processing {url}: {e}")
            await status_msg.edit_text(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            await status_msg.edit_text("❌ Tizimda xatolik yuz berdi. Iltimos keyinroq qayta urinib ko'ring.")
