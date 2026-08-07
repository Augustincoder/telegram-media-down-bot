import asyncio
import logging

from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired

from bot.utils.validators import INSTAGRAM_LINK_PATTERN

logger = logging.getLogger(__name__)


def get_challenge_code(username, choice):
    mode = "SMS" if choice == 1 else "Email"
    print(
        f"\n[DIQQAT] Instagram {username} uchun tasdiqlash kodini {mode} orqali yubordi!"
    )
    return input(f"Iltimos, {mode} ga kelgan 6 xonali kodni terminalga kiriting: ")


class InstagramService:
    def __init__(self):
        self.client = Client()
        self.client.challenge_code_handler = get_challenge_code
        self.is_logged_in = False

    async def login(
        self,
        session,
        username: str | None,
        password: str | None,
        session_id: str | None = None,
        session_json: str | None = None,
    ) -> bool:
        import json
        loop = asyncio.get_running_loop()

        # 1-variant: Agar to'liq session JSON berilgan bo'lsa (Eng ishonchli usul)
        if session_json:
            logger.info("Session JSON topildi. Uni ishlatib kirishga urinamiz...")
            try:
                settings = json.loads(session_json)
                self.client.set_settings(settings)
                # verify login state
                await loop.run_in_executor(None, self.client.get_timeline_feed)
                self.is_logged_in = True
                logger.info("Session JSON orqali muvaffaqiyatli kirildi!")
                return True
            except Exception as e:
                logger.warning(f"Session JSON orqali kirishda xatolik (Davom etamiz): {e}")

        # 2-variant: Faqat Session ID berilgan bo'lsa
        if session_id:
            logger.info("Session ID topildi. Uni ishlatib kirishga urinamiz...")
            try:
                await loop.run_in_executor(
                    None, self.client.login_by_sessionid, session_id
                )
                self.is_logged_in = True
                logger.info("Session ID orqali muvaffaqiyatli kirildi!")
                return True
            except Exception as e:
                logger.warning(f"Session ID orqali kirishda xatolik (Davom etamiz): {e}")

        if not username or not password:
            return False

        import json

        from sqlalchemy.future import select

        from bot.database.models import SystemState

        key = f"ig_session_{username}"
        state_res = await session.execute(
            select(SystemState).where(SystemState.key == key)
        )
        state = state_res.scalar_one_or_none()

        try:
            if state and state.value:
                self.client.set_settings(json.loads(state.value))

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.client.login, username, password)

            settings = self.client.get_settings()
            if not state:
                state = SystemState(key=key)
                session.add(state)
            state.value = json.dumps(settings)
            await session.commit()

            self.is_logged_in = True
            return True
        except ChallengeRequired:
            logger.error("Challenge Required! Could not resolve automatically.")
            return False
        except Exception as e:
            logger.error(f"Failed to login to Instagram via password (with settings): {e}")
            try:
                # Clear settings and try again
                logger.info("Trying to login without cached settings...")
                self.client.set_settings({})
                await loop.run_in_executor(None, self.client.login, username, password)
                
                settings = self.client.get_settings()
                if state:
                    state.value = json.dumps(settings)
                    await session.commit()
                
                self.is_logged_in = True
                return True
            except Exception as e2:
                logger.error(f"Failed to login even without settings: {e2}")
                return False

    async def _stream_media_items_concurrently(self, media_items: list[dict]):
        """Ichki yordamchi: Yuklab olish va jo'natishni parallel (stream) qilib beradi, tartibni saqlaydi."""
        total = len(media_items)
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
                        return None
                    result_item = item.copy()
                    result_item["data"] = data
                    return result_item
                except Exception as e:
                    logger.error(
                        f"Error downloading item {item['url'][:50]}...: {type(e).__name__} {e}"
                    )
                    return None

        # Natijalarni original tartibda kutish va yuborish
        # Xotirani to'ldirmaslik uchun har birini navbat bilan kutamiz
        for idx, item in enumerate(media_items, start=1):
            result = await download_item(item)
            if result:
                result["index"] = idx
                result["total"] = total
                yield result

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
            err_msg = str(e).lower()
            if "user_has_logged_out" in err_msg or "login_required" in err_msg or "403" in err_msg or "invalid request" in err_msg:
                self.is_logged_in = False
            logger.error(f"Unexpected error fetching info for {url}: {e}")
            return

        media_items = []
        
        meta_username = media_info.user.username if getattr(media_info, "user", None) else None
        meta_caption = media_info.caption_text if getattr(media_info, "caption_text", None) else None

        if media_info.media_type == 1:
            media_items.append({"type": "photo", "url": str(media_info.thumbnail_url), "username": meta_username, "caption": meta_caption, "source_url": url})
        elif media_info.media_type == 2:
            media_items.append({"type": "video", "url": str(media_info.video_url), "username": meta_username, "caption": meta_caption, "source_url": url})
        elif media_info.media_type == 8:
            for res in media_info.resources:
                if res.media_type == 1:
                    media_items.append({"type": "photo", "url": str(res.thumbnail_url), "username": meta_username, "caption": meta_caption, "source_url": url})
                elif res.media_type == 2:
                    media_items.append({"type": "video", "url": str(res.video_url), "username": meta_username, "caption": meta_caption, "source_url": url})

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
