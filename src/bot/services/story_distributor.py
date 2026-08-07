import logging
import os
from datetime import datetime

from aiogram import Bot
from aiogram.types import BufferedInputFile, FSInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.config import config
from bot.database.models import StoryCache
from bot.services.instagram import ig_service
from bot.services.telegram_userbot import userbot_service

logger = logging.getLogger(__name__)

def generate_story_caption(username: str, platform: str, posted_time: datetime | None = None) -> str:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    posted_str = posted_time.strftime("%Y-%m-%d %H:%M:%S") if posted_time else "Noma'lum"
    emoji = "📸" if platform == "instagram" else "✈️"
    
    caption = f"📥 <b>{username}</b> {emoji} hikoyasi\n"
    caption += "<blockquote expandable>"
    caption += f"<b>👤 Profil:</b> @{username}\n"
    caption += f"<b>🌐 Tarmoq:</b> {platform.capitalize()}\n"
    caption += f"<b>🕰 Qo'yilgan:</b> {posted_str}\n"
    caption += f"<b>💾 Saqlangan:</b> {now_str}"
    caption += "</blockquote>"
    
    return caption

async def distribute_ig_stories(
    bot: Bot,
    session: AsyncSession,
    stories: list,
    username: str,
    target_chat_id: int | None = None,
    status_msg: Message | None = None,
):
    """
    Instagram hikoyalarini yuklab, keshlab, kanalga saqlash va foydalanuvchiga yuborish
    (Spaghetti koddan qochish uchun markazlashtirilgan mantiq)
    """
    total = len(stories)
    sent_count = 0
    emoji = "📸"

    for idx, story in enumerate(stories, 1):
        if status_msg:
            await status_msg.edit_text(
                f"📥 <b>{username} {emoji}</b>: {idx}/{total} - hikoya tayyorlanmoqda..."
            )

        story_pk = str(story.pk)

        # Keshni tekshirish
        cache_res = await session.execute(
            select(StoryCache).where(
                StoryCache.story_id == story_pk,
                StoryCache.platform == "instagram",
            )
        )
        cached = cache_res.scalar_one_or_none()

        if cached and config.storage_channel_id:
            if target_chat_id:
                import contextlib
                with contextlib.suppress(Exception):
                    await bot.copy_message(
                        chat_id=target_chat_id,
                        from_chat_id=config.storage_channel_id,
                        message_id=cached.telegram_msg_id,
                    )
                    sent_count += 1
            continue

        # Agar keshda bo'lmasa, yuklaymiz
        media_items = []
        if story.media_type == 1:
            media_items.append({"type": "photo", "url": str(story.thumbnail_url)})
        elif story.media_type == 2:
            media_items.append({"type": "video", "url": str(story.video_url)})

        async for item in ig_service._stream_media_items_concurrently(media_items):
            file = BufferedInputFile(
                item["data"],
                filename=f"story.{'mp4' if item['type'] == 'video' else 'jpg'}",
            )
            
            caption = generate_story_caption(username, "instagram", getattr(story, "taken_at", None)) if not target_chat_id else None

            await _send_and_cache(
                bot, session, "instagram", username, story_pk, file, item["type"] == "video", target_chat_id, caption
            )
            sent_count += 1

    return sent_count

async def distribute_tg_stories(
    bot: Bot,
    session: AsyncSession,
    stories: list,
    username: str,
    target_chat_id: int | None = None,
    status_msg: Message | None = None,
    peer_id: str | int | None = None,
    access_hash: str | None = None,
):
    total = len(stories)
    sent_count = 0
    emoji = "✈️"
    
    download_peer = peer_id if peer_id else username

    for idx, story in enumerate(stories, 1):
        if status_msg:
            await status_msg.edit_text(
                f"📥 <b>{username} {emoji}</b>: {idx}/{total} - hikoya tayyorlanmoqda..."
            )
        
        story_id = str(story.id)

        # Keshni tekshirish
        cache_res = await session.execute(
            select(StoryCache).where(
                StoryCache.story_id == story_id,
                StoryCache.platform == "telegram",
            )
        )
        cached = cache_res.scalar_one_or_none()

        if cached and config.storage_channel_id:
            if target_chat_id:
                import contextlib
                with contextlib.suppress(Exception):
                    await bot.copy_message(
                        chat_id=target_chat_id,
                        from_chat_id=config.storage_channel_id,
                        message_id=cached.telegram_msg_id,
                    )
                    sent_count += 1
            continue

        file_path = f"downloads/tg_story_{username}_{story_id}.mp4"
        os.makedirs("downloads", exist_ok=True)
        try:
            downloaded = await userbot_service.download_story(download_peer, story.id, file_path, access_hash=access_hash)
            if downloaded:
                media = FSInputFile(downloaded)
                is_video = downloaded.endswith(".mp4")
                caption = generate_story_caption(username, "telegram", getattr(story, "date", None)) if not target_chat_id else None

                await _send_and_cache(
                    bot, session, "telegram", username, story_id, media, is_video, target_chat_id, caption
                )
                sent_count += 1
        except Exception as e:
            logger.error(f"TG hikoyani yuklashda xatolik: {e}")
        finally:
            import contextlib
            with contextlib.suppress(Exception):
                if 'downloaded' in locals() and downloaded:
                    os.remove(downloaded)
                if os.path.exists(file_path):
                    os.remove(file_path)

    return sent_count


async def _send_and_cache(
    bot: Bot,
    session: AsyncSession,
    platform: str,
    ig_username: str,
    story_id: str,
    media,
    is_video: bool,
    target_chat_id: int | None,
    caption: str | None,
):
    if config.storage_channel_id:
        # 1. Send to channel
        if is_video:
            msg = await bot.send_video(config.storage_channel_id, video=media, caption=caption)
        else:
            msg = await bot.send_photo(config.storage_channel_id, photo=media, caption=caption)
            
        # 2. Cache DB
        new_cache = StoryCache(
            platform=platform,
            ig_username=ig_username,
            story_id=story_id,
            telegram_msg_id=msg.message_id,
        )
        session.add(new_cache)
        await session.commit()
        
        # 3. Forward to user
        if target_chat_id:
            await bot.copy_message(
                chat_id=target_chat_id,
                from_chat_id=config.storage_channel_id,
                message_id=msg.message_id,
            )
    else:
        # No storage channel, send directly to user
        if target_chat_id:
            if is_video:
                await bot.send_video(target_chat_id, video=media, caption=caption)
            else:
                await bot.send_photo(target_chat_id, photo=media, caption=caption)
