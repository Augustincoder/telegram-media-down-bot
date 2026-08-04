import asyncio
import logging
import re
from bot.services.instagram import ig_service
from bot.services.pairing_cache import pairing_cache
from bot.database.models import InstagramPairing
from bot.database.session import AsyncSessionLocal
from bot.config import config
from aiogram import Bot

logger = logging.getLogger(__name__)

async def start_instagram_polling(bot: Bot):
    """
    Fon jarayoni (Background worker):
    1. Instagram Direct Inbox ni har 20 soniyada o'qiydi.
    2. Pairing kod kelsa, DB ga yozib bog'laydi.
    3. Video forward (uzatma) qilinsa, uni yuklab Telegramga yuboradi.
    """
    logger.info("Instagram DM polling worker started...")
    
    # Keshda oxirgi qayta ishlangan xabarlar ID sini saqlaymiz (to'liq ishlab qolmasligi uchun)
    processed_message_ids = set()
    
    MIN_SLEEP = 20
    MAX_SLEEP = 60
    current_sleep = MIN_SLEEP
    
    while True:
        try:
            found_new_messages = False
            loop = asyncio.get_running_loop()
            
            # Sinxron instagrapi metodini executor orqali asinxron chaqirish
            def fetch_inbox():
                try:
                    # pending: yangi, so'rovda turgan xabarlar
                    pending = ig_service.client.direct_pending_inbox(amount=5)
                    # threads: asosiy inboxdagi xabarlar
                    threads = ig_service.client.direct_threads(amount=5)
                    return pending + threads
                except Exception as e:
                    logger.error(f"Failed to fetch DM inbox: {e}")
                    return []

            threads = await loop.run_in_executor(None, fetch_inbox)
            
            if threads:
                async with AsyncSessionLocal() as session:
                    for thread in threads:
                        if not thread.messages:
                            continue
                            
                        # Har bir thread ning faqat eng oxirgi xabarini olamiz
                        msg = thread.messages[0]
                        
                        if msg.id in processed_message_ids:
                            continue
                            
                        # Agar biz yuborgan bo'lsak, tashlab o'tamiz
                        if msg.user_id == ig_service.client.user_id:
                            processed_message_ids.add(msg.id)
                            continue
                            
                        found_new_messages = True
                        sender_id = str(msg.user_id)
                        
                        # LOGIKA 1: PAIRING KOD
                        if msg.item_type == "text":
                            text = msg.text.strip()
                            if re.match(r"^\d{6}$", text):
                                code = text
                                tg_user_id = pairing_cache.verify_code(code)
                                
                                if tg_user_id:
                                    # Bog'lanishni saqlash
                                    new_pairing = InstagramPairing(
                                        user_id=tg_user_id, 
                                        instagram_user_id=sender_id,
                                        instagram_username=thread.users[0].username if thread.users else None
                                    )
                                    session.add(new_pairing)
                                    try:
                                        await session.commit()
                                        logger.info(f"Successfully paired IG {sender_id} with TG {tg_user_id}")
                                        
                                        # Foydalanuvchiga Telegram orqali xabar
                                        await bot.send_message(
                                            tg_user_id, 
                                            f"🎉 <b>Muvaffaqiyatli!</b>\nInstagram akkauntingiz bog'landi. Endi do'stlaringiz sizga Direct orqali ulashgan videolarni ham xuddi shu <b>{config.instagram_username}</b> profiliga DM qilib tashlang va men uni shu yerga yuklab beraman!"
                                        )
                                        
                                        # Foydalanuvchiga Instagram orqali javob
                                        def reply_ig():
                                            ig_service.client.direct_send(
                                                "Muvaffaqiyatli bog'landi ✅ Endi videolarni Direct orqali shu yerga yuborishingiz mumkin.", 
                                                user_ids=[sender_id]
                                            )
                                        await loop.run_in_executor(None, reply_ig)
                                        
                                    except Exception as e:
                                        logger.error(f"Pairing saqlashda xato: {e}")
                                        await session.rollback()
                        
                        # LOGIKA 2: FORWARD QILINGAN REELS/VIDEO
                        elif msg.item_type in ["clip", "media_share", "xma_media_share", "xma_clip", "xma_story_share", "story_share"]:
                            # Bu media qaysi foydalanuvchidan keldi? (DB dan tekshiramiz)
                            from sqlalchemy.future import select
                            result = await session.execute(
                                select(InstagramPairing).where(InstagramPairing.instagram_user_id == sender_id).limit(1)
                            )
                            pairing = result.scalar_one_or_none()
                            
                            if pairing and pairing.is_active:
                                tg_user_id = pairing.user_id
                                
                                media_url = None
                                
                                if msg.item_type in ["xma_clip", "xma_media_share", "xma_story_share"]:
                                    if hasattr(msg, "xma_share") and msg.xma_share and isinstance(msg.xma_share, dict):
                                        media_url = msg.xma_share.get('video_url') or msg.xma_share.get('target_url')
                                    if not media_url and hasattr(msg, "raw_xma") and msg.raw_xma and isinstance(msg.raw_xma, dict):
                                        for key in msg.raw_xma:
                                            if isinstance(msg.raw_xma[key], list) and len(msg.raw_xma[key]) > 0:
                                                media_url = msg.raw_xma[key][0].get('target_url')
                                                if media_url: break

                                elif msg.item_type == "clip" and hasattr(msg, "clip") and msg.clip:
                                    media_id = getattr(msg.clip, "id", None) or getattr(msg.clip, "pk", None)
                                    if media_id: media_url = f"https://instagram.com/p/{str(media_id).split('_')[0]}/"
                                    
                                elif msg.item_type in ["media_share", "story_share"] and hasattr(msg, "media_share") and msg.media_share:
                                    media_id = getattr(msg.media_share, "id", None) or getattr(msg.media_share, "pk", None)
                                    if media_id: media_url = f"https://instagram.com/p/{str(media_id).split('_')[0]}/"
                                
                                # Agar url topilsa tortishni boshlaymiz
                                if media_url:
                                    logger.info(f"Downloading forwarded media {media_url} for TG {tg_user_id}")
                                    try:    
                                        # IG Service orqali stream yuklab Telegramga jo'natamiz
                                        from bot.handlers.messages import send_cached_items_individually
                                        from aiogram.types import BufferedInputFile
                                        from aiogram.exceptions import TelegramRetryAfter
                                        
                                        await bot.send_message(tg_user_id, f"📥 Uzatma (Forward) qabul qilindi, yuklanmoqda...")
                                        
                                        async for item in ig_service.stream_instagram_media(media_url):
                                            total = item.get("total", 1)
                                            idx = item.get("index", 1)
                                            caption = f"📥 Direct media ({idx}/{total})" if total > 1 else "📥 Direct media"
                                            
                                            file = BufferedInputFile(item["data"], filename=f"media.{'mp4' if item['type'] == 'video' else 'jpg'}")
                                            
                                            while True:
                                                try:
                                                    if item["type"] == "video":
                                                        await bot.send_video(tg_user_id, file, caption=caption)
                                                    else:
                                                        await bot.send_photo(tg_user_id, file, caption=caption)
                                                    
                                                    await asyncio.sleep(0.5)
                                                    break
                                                except TelegramRetryAfter as e:
                                                    logger.warning(f"Flood control in DM poll. Sleeping {e.retry_after}s.")
                                                    await asyncio.sleep(e.retry_after + 1)
                                                
                                    except Exception as e:
                                        logger.error(f"Forward qilingan mediani tortishda xato: {e}")
                                        await bot.send_message(tg_user_id, "❌ Mediani tortishda xatolik yuz berdi. Balki uzatma (media) yashiringan yoki o'chirilgandir.")
                                
                        # Xabarni o'qilgan belgisi
                        processed_message_ids.add(msg.id)
                        # Xotirani tejash uchun set hajmini cheklash (1000 tadan oshmasin)
                        if len(processed_message_ids) > 1000:
                            processed_message_ids = set(list(processed_message_ids)[-500:])
                            
        except Exception as e:
            logger.error(f"DM Polling iteratsiyasida xato: {e}")
            
        # Dinamik (aqlli) sleep logikasi
        if found_new_messages:
            current_sleep = MIN_SLEEP
        else:
            current_sleep = min(current_sleep + 10, MAX_SLEEP)
            
        await asyncio.sleep(current_sleep)
