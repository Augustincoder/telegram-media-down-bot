import asyncio
import logging
from typing import Optional
import aiohttp
from instagrapi import Client
from instagrapi.exceptions import ClientError, ChallengeRequired
from aiogram.types import BufferedInputFile

from bot.utils.validators import INSTAGRAM_REEL_PATTERN

logger = logging.getLogger(__name__)

def get_challenge_code(username, choice):
    mode = "SMS" if choice == 1 else "Email"
    print(f"\n[DIQQAT] Instagram {username} uchun tasdiqlash kodini {mode} orqali yubordi!")
    code = input(f"Iltimos, {mode} ga kelgan 6 xonali kodni terminalga kiriting: ")
    return code

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

    async def download_reel_bytes(self, url: str) -> Optional[bytes]:
        loop = asyncio.get_running_loop()
        
        # O(1) tezlikda URL ichidan shortcode ni ajratib olamiz (Tarmoq so'rovisiz)
        match = INSTAGRAM_REEL_PATTERN.search(url)
        if not match:
            raise ValueError("Noto'g'ri havola formati")
        shortcode = match.group(1)

        # 1. Ma'lumotlarni olish (Faqat bitta API so'rov)
        def fetch_media_info():
            media_pk = self.client.media_pk_from_url(url)
            return self.client.media_info(media_pk)

        try:
            media_info = await loop.run_in_executor(None, fetch_media_info)
        except ClientError as e:
            logger.error(f"Instagrapi ClientError downloading {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching info for {url}: {e}")
            return None

        # 2. Video URL ni ajratib olish
        video_url = None
        if media_info.media_type == 2:  # 2 = Video
            video_url = str(media_info.video_url) if media_info.video_url else None
        elif media_info.media_type == 8:  # 8 = Album/Carousel
            for res in media_info.resources:
                if res.media_type == 2:
                    video_url = str(res.video_url) if res.video_url else None
                    break
        
        if not video_url:
            raise ValueError("Bunday postni yuklab bo'lmaydi (Faqat bitta dona video/reels yuboring)")

        # 3. Diskka yozmasdan to'g'ridan-to'g'ri RAM (Xotira) ga asinxron tortish! 
        # Bu tezlikni juda oshiradi, chunki Hard Disk/SSD (I/O) qatnashmaydi.
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(video_url) as resp:
                    if resp.status == 200:
                        video_bytes = await resp.read()
                        
                        # Fayl hajmini RAMda tekshiramiz (< 50MB)
                        if len(video_bytes) > 49.5 * 1024 * 1024:
                            logger.warning(f"File too large: {len(video_bytes)/1024/1024:.2f}MB")
                            return None
                        return video_bytes
                    else:
                        logger.error(f"Failed to download video file. HTTP {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Error during async in-memory download of {url}: {e}")
            return None

# Singleton instance
ig_service = InstagramService()
