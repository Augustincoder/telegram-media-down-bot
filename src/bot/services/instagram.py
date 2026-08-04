import asyncio
import logging
from typing import Optional
import aiohttp
from instagrapi import Client
from instagrapi.exceptions import ClientError, ChallengeRequired
from bot.utils.validators import INSTAGRAM_LINK_PATTERN

logger = logging.getLogger(__name__)

def get_challenge_code(username, choice):
    mode = "SMS" if choice == 1 else "Email"
    print(f"\n[DIQQAT] Instagram {username} uchun tasdiqlash kodini {mode} orqali yubordi!")
    return input(f"Iltimos, {mode} ga kelgan 6 xonali kodni terminalga kiriting: ")

class InstagramService:
    def __init__(self):
        self.client = Client()
        self.client.challenge_code_handler = get_challenge_code
        self.is_logged_in = False

    def login(self, username: Optional[str], password: Optional[str], session_id: Optional[str] = None) -> bool:
        if session_id:
            logger.info("Session ID topildi. Uni ishlatib kirishga urinamiz...")
            try:
                self.client.login_by_sessionid(session_id)
                self.is_logged_in = True
                logger.info("Session ID orqali muvaffaqiyatli kirildi!")
                return True
            except Exception as e:
                logger.error(f"Session ID orqali kirishda xatolik: {e}")
                return False

        if not username or not password:
            return False
            
        import pathlib
        session_file = pathlib.Path(f"instagram_session_{username}.json")
        try:
            if session_file.exists():
                self.client.load_settings(session_file)
            self.client.login(username, password)
            self.client.dump_settings(session_file)
            self.is_logged_in = True
            return True
        except ChallengeRequired as e:
            logger.error(f"Challenge Required! Could not resolve automatically.")
            return False
        except Exception as e:
            logger.error(f"Failed to login to Instagram via password: {e}")
            return False

    async def get_instagram_media(self, url: str) -> list[dict]:
        """Bitta post/reel/karusel ichidagi barcha medialarni (video/rasm) xotiraga tortib qaytaradi."""
        loop = asyncio.get_running_loop()
        
        match = INSTAGRAM_LINK_PATTERN.search(url)
        if not match:
            raise ValueError("Noto'g'ri havola formati")

        def fetch_media_info():
            media_pk = self.client.media_pk_from_url(url)
            return self.client.media_info(media_pk)

        try:
            media_info = await loop.run_in_executor(None, fetch_media_info)
        except ClientError as e:
            logger.error(f"Instagrapi ClientError downloading {url}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching info for {url}: {e}")
            return []

        # Turlarga qarab URL'larni ajratib olamiz
        media_items = []
        if media_info.media_type == 1:  # Photo
            media_items.append({"type": "photo", "url": str(media_info.thumbnail_url)})
        elif media_info.media_type == 2:  # Video
            media_items.append({"type": "video", "url": str(media_info.video_url)})
        elif media_info.media_type == 8:  # Carousel (Album)
            for res in media_info.resources:
                if res.media_type == 1:
                    media_items.append({"type": "photo", "url": str(res.thumbnail_url)})
                elif res.media_type == 2:
                    media_items.append({"type": "video", "url": str(res.video_url)})
        
        if not media_items:
            raise ValueError("Post ichida hech qanday tasdiqlangan media topilmadi")

        # Barcha medialarni parallel (bir vaqtda) yuklaymiz!
        async def download_item(item):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(item["url"]) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if len(data) > 49.5 * 1024 * 1024:
                                return None
                            return {"type": item["type"], "data": data}
            except Exception as e:
                logger.error(f"Error downloading item {item['url']}: {e}")
            return None

        # Asinxron parallel yuklash (Karusel 10ta bo'lsa ham tez tortadi)
        results = await asyncio.gather(*(download_item(item) for item in media_items))
        
        final_media = [r for r in results if r is not None]
        if not final_media:
            raise ValueError("Medialarni yuklashda xatolik yuz berdi (hajmi katta bo'lishi mumkin)")
            
        return final_media

ig_service = InstagramService()
