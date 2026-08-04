import asyncio
import logging
import json
from datetime import datetime, timedelta, timezone
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

    # ==========================
    # 1. POST/REEL/KARUSEL KESHLASH VA YUKLASH
    # ==========================
    if url:
        # Baza keshi (Faqat to'g'ri saqlangan fayllarni izlaymiz)
        result = await session.execute(
            select(Download).where(Download.url == url).where(Download.file_id != None).limit(1)
        )
        cached_download = result.scalar_one_or_none()

        if cached_download and cached_download.file_id:
            logger.info(f"Cache hit for {url}")
            try:
                # Agar yakka video/rasm bo'lsa
                if cached_download.media_type == "video":
                    await message.answer_video(cached_download.file_id)
                    return
                elif cached_download.media_type == "photo":
                    await message.answer_photo(cached_download.file_id)
                    return
                # Agar karusel (albom) bo'lsa (JSON o'qiymiz)
                elif cached_download.media_type == "carousel":
                    media_list = json.loads(cached_download.file_id)
                    media_group = MediaGroupBuilder(caption="📥 Yuklab olindi (Keshdan)")
                    for item in media_list:
                        if item["type"] == "video":
                            media_group.add_video(media=item["file_id"])
                        else:
                            media_group.add_photo(media=item["file_id"])
                    await message.answer_media_group(media_group.build())
                    return
            except Exception as e:
                logger.error(f"Cache o'qishda xatolik: {e}")
                # Kesh buzilgan bo'lsa, davom etib yangidan yuklaydi

        status_msg = await message.answer("⚡ Media yuklanmoqda...")
        async with download_semaphore:
            try:
                media_items = await ig_service.get_instagram_media(url)
                if not media_items:
                    await status_msg.edit_text("❌ Mediani yuklab olishni imkoni bo'lmadi.")
                    return

                # Agar faqat bitta rasm/video bo'lsa
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
                # Agar karusel bo'lsa
                else:
                    media_group = MediaGroupBuilder(caption="📥 Karusel yuklab olindi")
                    for idx, item in enumerate(media_items):
                        file = BufferedInputFile(item["data"], filename=f"media_{idx}.{'mp4' if item['type']=='video' else 'jpg'}")
                        if item["type"] == "video":
                            media_group.add_video(media=file)
                        else:
                            media_group.add_photo(media=file)
                    
                    sent_msgs = await message.answer_media_group(media_group.build())
                    
                    # Barcha fayl ID larini JSON formatida keshga saqlaymiz
                    file_ids_data = []
                    for m in sent_msgs:
                        if m.video:
                            file_ids_data.append({"type": "video", "file_id": m.video.file_id})
                        elif m.photo:
                            file_ids_data.append({"type": "photo", "file_id": m.photo[-1].file_id})
                            
                    cached_file_id_str = json.dumps(file_ids_data)
                    new_dl = Download(user_id=user_id, platform="instagram", media_type="carousel", url=url, file_id=cached_file_id_str)
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

    # ==========================
    # 2. HIKOYALAR (STORIES) KESHLASH VA YUKLASH
    # ==========================
    username = extract_instagram_username(text)
    if username:
        # Hikoyalar 24 soat ichida yo'qoladi va tez-tez yangilanadi.
        # Shu sababli profillarni faqat 10 daqiqa muddatga keshlaymiz (Spam va akkaunt bloklanishidan himoya)
        time_threshold = datetime.now(timezone.utc) - timedelta(minutes=10)
        
        result = await session.execute(
            select(Download)
            .where(Download.url == f"story_{username}")
            .where(Download.file_id != None)
            .where(Download.created_at >= time_threshold)
            .order_by(Download.created_at.desc())
            .limit(1)
        )
        cached_story = result.scalar_one_or_none()

        if cached_story and cached_story.file_id:
            logger.info(f"Story cache hit for {username}")
            try:
                story_batches = json.loads(cached_story.file_id)
                for batch in story_batches:
                    media_group = MediaGroupBuilder(caption=f"📥 @{username} hikoyalari (Keshdan)")
                    for item in batch:
                        if item["type"] == "video":
                            media_group.add_video(media=item["file_id"])
                        else:
                            media_group.add_photo(media=item["file_id"])
                    await message.answer_media_group(media_group.build())
                return
            except Exception as e:
                logger.error(f"Story cache o'qishda xatolik: {e}")

        status_msg = await message.answer(f"⚡ @{username} profili tahlil qilinmoqda...")
        async with download_semaphore:
            try:
                stories = await ig_service.get_user_stories(username)
                if not stories:
                    await status_msg.edit_text(f"❌ @{username} profilida so'nggi 24 soat ichida hikoyalar topilmadi yoki profil yopiq (Private).")
                    return

                await status_msg.edit_text(f"⚡ @{username} profilidan jami {len(stories)} ta hikoya topildi, yuklanmoqda...")
                
                all_sent_batches = []
                for i in range(0, len(stories), 10):
                    chunk = stories[i:i+10]
                    if len(chunk) == 1:
                        item = chunk[0]
                        file = BufferedInputFile(item["data"], filename=f"story.{'mp4' if item['type'] == 'video' else 'jpg'}")
                        if item["type"] == "video":
                            sent_msg = await message.answer_video(file, caption=f"📥 @{username} hikoyasi")
                            all_sent_batches.append([{"type": "video", "file_id": sent_msg.video.file_id}])
                        else:
                            sent_msg = await message.answer_photo(file, caption=f"📥 @{username} hikoyasi")
                            all_sent_batches.append([{"type": "photo", "file_id": sent_msg.photo[-1].file_id}])
                    else:
                        media_group = MediaGroupBuilder(caption=f"📥 @{username} hikoyalari")
                        for idx, item in enumerate(chunk):
                            file = BufferedInputFile(item["data"], filename=f"story_{idx}.{'mp4' if item['type']=='video' else 'jpg'}")
                            if item["type"] == "video":
                                media_group.add_video(media=file)
                            else:
                                media_group.add_photo(media=file)
                        
                        sent_msgs = await message.answer_media_group(media_group.build())
                        
                        # Kesh uchun fayllar ro'yxati
                        batch_ids = []
                        for m in sent_msgs:
                            if m.video:
                                batch_ids.append({"type": "video", "file_id": m.video.file_id})
                            elif m.photo:
                                batch_ids.append({"type": "photo", "file_id": m.photo[-1].file_id})
                        all_sent_batches.append(batch_ids)

                # Barcha stories keshini JSON array'lar qatori sifatida bitta xatorda saqlaymiz
                new_dl = Download(
                    user_id=user_id, 
                    platform="instagram", 
                    media_type="stories", 
                    url=f"story_{username}", 
                    file_id=json.dumps(all_sent_batches)
                )
                session.add(new_dl)
                await session.commit()
                
                await status_msg.delete()
            except Exception as e:
                logger.error(f"Error processing stories for {username}: {e}")
                await status_msg.edit_text("❌ Hikoyalarni yuklashda xatolik yuz berdi.")
        return
