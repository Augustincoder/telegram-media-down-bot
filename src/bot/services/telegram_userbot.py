import logging
import os

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.stories import GetPeerStoriesRequest, GetStoriesByIDRequest

from bot.config import config

logger = logging.getLogger(__name__)


class TelegramUserbot:
    def __init__(self):
        self.client = None
        self.is_connected = False

    async def start(self):
        if (
            not config.telegram_api_id
            or not config.telegram_api_hash
            or not config.telegram_userbot_session_string
        ):
            logger.warning(
                "Telegram Userbot credentials not fully provided. Userbot will not start."
            )
            return

        try:
            from telethon.sessions import SQLiteSession, StringSession
            session = SQLiteSession("telegram_userbot_session")
            if not session.server_address and config.telegram_userbot_session_string:
                try:
                    str_sess = StringSession(config.telegram_userbot_session_string)
                    session.set_dc(str_sess.dc_id, str_sess.server_address, str_sess.port)
                    session.auth_key = str_sess.auth_key
                    logger.info("Migrated StringSession to SQLiteSession.")
                except Exception as e:
                    logger.warning(f"Could not migrate StringSession: {e}")

            self.client = TelegramClient(
                session,
                config.telegram_api_id,
                config.telegram_api_hash,
            )
            await self.client.connect()
            if await self.client.is_user_authorized():
                self.is_connected = True
                me = await self.client.get_me()
                logger.info(f"Userbot muvaffaqiyatli ishga tushdi: @{me.username}")
            else:
                logger.error("Userbot sessiyasi yaroqsiz! Qaytadan login qiling.")
        except Exception as e:
            logger.error(f"Userbot ni ishga tushirishda xatolik: {e}")

    async def stop(self):
        if self.client and self.is_connected:
            await self.client.disconnect()
            self.is_connected = False

    async def download_story(
        self, peer: str, story_id: int, file_path: str, access_hash: str | None = None
    ) -> str | None:
        """
        Telegram story'ni yuklab olish
        peer: username (masalan, 'durov') yoki telefon raqami
        story_id: 1, 2, 3 kabi story ID
        """
        if not self.is_connected:
            raise Exception("Userbot ishga tushirilmagan. Story yuklab bo'lmaydi.")

        try:
            # Username/peer ni telethon entitiy'ga o'tkazamiz
            peer_id = int(peer) if str(peer).lstrip('-').isdigit() else peer
            if isinstance(peer_id, int) and access_hash:
                from telethon.tl.types import InputPeerUser
                entity = InputPeerUser(user_id=peer_id, access_hash=int(access_hash))
            else:
                entity = await self.client.get_input_entity(peer_id)

            # Story'ni olish
            result = await self.client(
                GetStoriesByIDRequest(peer=entity, id=[story_id])
            )

            if not result.stories:
                return None

            story = result.stories[0]

            # Yuklab olish
            logger.info(f"Yuklanmoqda: @{peer} -> story {story_id}")
            downloaded_file = await self.client.download_media(
                story.media, file=file_path
            )

            return downloaded_file
        except Exception as e:
            logger.error(f"Telegram hikoyasini yuklashda xato: {e}")
            raise e

    async def stream_all_stories(self, peer: str, dir_path: str):
        """
        Guvohnoma/username'dagi barcha aktiv storylarni yuklab olish.
        Qaytaradi: yuklangan fayllar manzillari oqimi (generator).
        """
        if not self.is_connected:
            raise Exception("Userbot ishga tushirilmagan. Story yuklab bo'lmaydi.")

        try:
            peer_id = int(peer) if str(peer).lstrip('-').isdigit() else peer
            entity = await self.client.get_input_entity(peer_id)
            result = await self.client(GetPeerStoriesRequest(peer=entity))

            if not result.stories or not result.stories.stories:
                return

            for story in result.stories.stories:
                file_path = os.path.join(dir_path, f"tg_story_{peer}_{story.id}.mp4")
                dl_file = await self.client.download_media(story.media, file=file_path)
                if dl_file:
                    yield dl_file
        except Exception as e:
            logger.error(f"Telegram foydalanuvchisi hikoyalarini yuklashda xato: {e}")
            raise e

    async def get_peer_stories_info(self, peer: str, access_hash: str | None = None) -> list:
        """Faqat story obyektlarini (metadata) qaytaradi, yuklamaydi."""
        if not self.is_connected:
            return []
        try:
            peer_id = int(peer) if str(peer).lstrip('-').isdigit() else peer
            if isinstance(peer_id, int) and access_hash:
                from telethon.tl.types import InputPeerUser
                entity = InputPeerUser(user_id=peer_id, access_hash=int(access_hash))
            else:
                entity = await self.client.get_input_entity(peer_id)
            
            result = await self.client(GetPeerStoriesRequest(peer=entity))
            if not result.stories or not result.stories.stories:
                return []
            return result.stories.stories
        except Exception as e:
            logger.error(f"Telegram hikoyalar metadata sini olishda xato: {e}")
            return []

    async def download_message_media(self, peer: str, message_id: int, file_path: str) -> str | None:
        """
        Telegram post media yuklab olish
        (Yopiq va saqlash taqiqlangan postlar uchun ham ishlaydi).
        """
        if not self.is_connected:
            raise Exception("Userbot ishga tushirilmagan.")
        try:
            peer_id = int(peer) if str(peer).lstrip('-').isdigit() else peer
            entity = await self.client.get_input_entity(peer_id)
            messages = await self.client.get_messages(entity, ids=[message_id])
            if not messages or not messages[0]:
                return None
            
            message = messages[0]
            if not message.media:
                return None

            logger.info(f"Downloading post media: {peer} -> {message_id}")
            downloaded_file = await self.client.download_media(message, file=file_path)
            return downloaded_file
        except Exception as e:
            logger.error(f"Failed to download message media {peer}/{message_id}: {e}")
            raise e

userbot_service = TelegramUserbot()

