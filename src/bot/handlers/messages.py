import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.utils.media_group import MediaGroupBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.utils.validators import extract_instagram_url, extract_instagram_username
from bot.services.instagram import ig_service
from bot.database.models import Download

logger = logging.getLogger(__name__)
router = Router(name="messages")

download_semaphore = asyncio.Semaphore(3)

@router.message(F.text)
async def process_text_message(message: Message, session: AsyncSession):
    text = message.text
    url = extract_instagram_url(text)
    user_id = message.from_user.id

    # 1. Agar xabar POST/REEL havolasi bo'lsa
    if url:
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
                media_items = await ig_service.get_instagram_media(url)
                if not media_items:
                    await status_msg.edit_text("❌ Mediani yuklab olishni imkoni bo'lmadi.")
                    return

                if len(media_items) == 1:
                    item = media_items[0]
                    file = BufferedInputFile(item["data"], filename=f"file.{'mp4' if item['type'] == 'video' else 'jpg'}")
                    if item["type"] == "video":
                        sent_msg = await message.answer_video(file, caption="📥 Yuklab olindi")
                        file_id = sent_msg.video.file_id
                    else:
                        sent_msg = await message.answer_photo(file, caption="📥 Yuklab olindi")
                        file_id = sent_msg.photo[-1].file_id
                        
                    new_dl = Download(user_id=user_id, platform="instagram", media_type=item["type"], url=url, file_id=file_id)
                    session.add(new_dl)
                    await session.commit()
                else:
                    media_group = MediaGroupBuilder(caption="📥 Karusel yuklab olindi")
                    for idx, item in enumerate(media_items):
                        file = BufferedInputFile(item["data"], filename=f"media_{idx}.{'mp4' if item['type']=='video' else 'jpg'}")
                        if item["type"] == "video":
                            media_group.add_video(media=file)
                        else:
                            media_group.add_photo(media=file)
                    
                    await message.answer_media_group(media_group.build())
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
        return

    # 2. Agar xabar STORY havolasi (yoki oddiy profil) bo'lsa
    username = extract_instagram_username(text)
    if username:
        status_msg = await message.answer(f"⚡ @{username} profili tahlil qilinmoqda...")
        async with download_semaphore:
            try:
                stories = await ig_service.get_user_stories(username)
                if not stories:
                    await status_msg.edit_text(f"❌ @{username} profilida so'nggi 24 soat ichida hikoyalar topilmadi yoki profil yopiq (Private).")
                    return

                await status_msg.edit_text(f"⚡ @{username} profilidan jami {len(stories)} ta hikoya topildi, yuklanmoqda...")
                
                # Telegram bitta xabarda faqat 10 ta media yuborishga ruxsat beradi (MediaGroup limit)
                # Shuning uchun hikoyalarni 10 tadan bo'lib yuboramiz
                for i in range(0, len(stories), 10):
                    chunk = stories[i:i+10]
                    if len(chunk) == 1:
                        item = chunk[0]
                        file = BufferedInputFile(item["data"], filename=f"story.{'mp4' if item['type'] == 'video' else 'jpg'}")
                        if item["type"] == "video":
                            await message.answer_video(file, caption=f"📥 @{username} hikoyasi")
                        else:
                            await message.answer_photo(file, caption=f"📥 @{username} hikoyasi")
                    else:
                        media_group = MediaGroupBuilder(caption=f"📥 @{username} hikoyalari")
                        for idx, item in enumerate(chunk):
                            file = BufferedInputFile(item["data"], filename=f"story_{idx}.{'mp4' if item['type']=='video' else 'jpg'}")
                            if item["type"] == "video":
                                media_group.add_video(media=file)
                            else:
                                media_group.add_photo(media=file)
                        
                        await message.answer_media_group(media_group.build())
                
                await status_msg.delete()
            except Exception as e:
                logger.error(f"Error processing stories for {username}: {e}")
                await status_msg.edit_text("❌ Hikoyalarni yuklashda xatolik yuz berdi.")
        return
