from aiogram.types import Message, BufferedInputFile
from aiogram.utils.media_group import MediaGroupBuilder

async def send_downloaded_media(message: Message, media_items: list[dict], caption: str) -> list[dict]:
    """
    Xotiradagi (bytes) media elementlarini foydalanuvchiga yuboradi (1 ta yoki 10 tadan guruhlab).
    Telegram'ga yuklangan fayllarning file_id larini qaytaradi (keshlash uchun).
    """
    sent_file_ids = []
    
    # Telegram bitta xabarda eng ko'pi bilan 10 ta media (MediaGroup) qabul qiladi
    for i in range(0, len(media_items), 10):
        chunk = media_items[i:i+10]
        
        if len(chunk) == 1:
            item = chunk[0]
            filename = f"media.{'mp4' if item['type'] == 'video' else 'jpg'}"
            file = BufferedInputFile(item["data"], filename=filename)
            
            if item["type"] == "video":
                sent_msg = await message.answer_video(file, caption=caption)
                sent_file_ids.append({"type": "video", "file_id": sent_msg.video.file_id})
            else:
                sent_msg = await message.answer_photo(file, caption=caption)
                sent_file_ids.append({"type": "photo", "file_id": sent_msg.photo[-1].file_id})
        else:
            media_group = MediaGroupBuilder(caption=caption)
            for idx, item in enumerate(chunk):
                filename = f"media_{idx}.{'mp4' if item['type'] == 'video' else 'jpg'}"
                file = BufferedInputFile(item["data"], filename=filename)
                
                if item["type"] == "video":
                    media_group.add_video(media=file)
                else:
                    media_group.add_photo(media=file)
            
            sent_msgs = await message.answer_media_group(media_group.build())
            
            for m in sent_msgs:
                if m.video:
                    sent_file_ids.append({"type": "video", "file_id": m.video.file_id})
                elif m.photo:
                    sent_file_ids.append({"type": "photo", "file_id": m.photo[-1].file_id})
                    
    return sent_file_ids

async def send_cached_media(message: Message, file_ids: list[dict], caption: str):
    """
    Keshdagi (file_id) media elementlarini foydalanuvchiga tezkor yuboradi.
    """
    for i in range(0, len(file_ids), 10):
        chunk = file_ids[i:i+10]
        
        if len(chunk) == 1:
            item = chunk[0]
            if item["type"] == "video":
                await message.answer_video(item["file_id"], caption=caption)
            else:
                await message.answer_photo(item["file_id"], caption=caption)
        else:
            media_group = MediaGroupBuilder(caption=caption)
            for item in chunk:
                if item["type"] == "video":
                    media_group.add_video(media=item["file_id"])
                else:
                    media_group.add_photo(media=item["file_id"])
            
            await message.answer_media_group(media_group.build())
