import asyncio
import logging
from typing import Optional
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

    async def _stream_media_items_concurrently(self, media_items: list[dict]):
        """Ichki yordamchi: Yuklab olish va jo'natishni parallel (stream) qilib beradi."""
        queue = asyncio.Queue()
        
        async def producer():
            sem = asyncio.Semaphore(2)
            loop = asyncio.get_running_loop()
            
            def fetch_bytes(download_url: str) -> bytes:
                resp = self.client.public.get(download_url, stream=True, timeout=15)
                resp.raise_for_status()
                data = bytearray()
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        data.extend(chunk)
                    if len(data) > 49.5 * 1024 * 1024:
                        break
                return bytes(data)

            async def download_item(item):
                async with sem:
                    try:
                        data = await loop.run_in_executor(None, fetch_bytes, item["url"])
                        if len(data) > 49.5 * 1024 * 1024:
                            logger.warning(f"File too large for {item['url'][:50]}...")
                            await queue.put(None)
                            return
                        await queue.put({"type": item["type"], "data": data})
                    except Exception as e:
                        logger.error(f"Error downloading item {item['url'][:50]}...: {type(e).__name__} {e}")
                        await queue.put(None)

            await asyncio.gather(*(download_item(item) for item in media_items))
            await queue.put("DONE")

        # Orqa fonda yuklashni boshlaymiz
        asyncio.create_task(producer())

        # Tayyor bo'lganlarini bittalab (stream) qaytaramiz
        while True:
            item = await queue.get()
            if item == "DONE":
                break
            if item is not None:
                yield item

    async def stream_instagram_media(self, url: str):
        """Bitta post/reel/karusel medialarini oqim (stream) qilib qaytaradi."""
        loop = asyncio.get_running_loop()
        
        match = INSTAGRAM_LINK_PATTERN.search(url)
        if not match:
            raise ValueError("Noto'g'ri havola formati")

        def fetch_media_info():
            media_pk = self.client.media_pk_from_url(url)
            return self.client.media_info(media_pk)

        try:
            media_info = await loop.run_in_executor(None, fetch_media_info)
        except Exception as e:
            logger.error(f"Unexpected error fetching info for {url}: {e}")
            return

        media_items = []
        if media_info.media_type == 1:
            media_items.append({"type": "photo", "url": str(media_info.thumbnail_url)})
        elif media_info.media_type == 2:
            media_items.append({"type": "video", "url": str(media_info.video_url)})
        elif media_info.media_type == 8:
            for res in media_info.resources:
                if res.media_type == 1:
                    media_items.append({"type": "photo", "url": str(res.thumbnail_url)})
                elif res.media_type == 2:
                    media_items.append({"type": "video", "url": str(res.video_url)})
        
        if not media_items:
            raise ValueError("Post ichida hech qanday tasdiqlangan media topilmadi")

        async for item in self._stream_media_items_concurrently(media_items):
            yield item

    async def stream_user_stories(self, username: str):
        """Berilgan foydalanuvchining hikoyalarini oqim (stream) qilib qaytaradi."""
        loop = asyncio.get_running_loop()
        
        def fetch_stories():
            user_id = self.client.user_id_from_username(username)
            return self.client.user_stories(user_id)

        try:
            stories = await loop.run_in_executor(None, fetch_stories)
        except Exception as e:
            logger.error(f"Error fetching stories for {username}: {e}")
            return
            
        if not stories:
            return

        media_items = []
        for story in stories:
            if story.media_type == 1:
                media_items.append({"type": "photo", "url": str(story.thumbnail_url)})
            elif story.media_type == 2:
                media_items.append({"type": "video", "url": str(story.video_url)})
                
        async for item in self._stream_media_items_concurrently(media_items):
            yield item

ig_service = InstagramService()
