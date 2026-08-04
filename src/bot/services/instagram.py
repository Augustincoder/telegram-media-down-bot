import asyncio
import logging
from pathlib import Path
from typing import Optional
from instagrapi import Client
from instagrapi.exceptions import ClientError

logger = logging.getLogger(__name__)

class InstagramService:
    def __init__(self):
        self.client = Client()
        self.is_logged_in = False

    def login(self, username: str, password: str) -> bool:
        if not username or not password:
            logger.warning("No Instagram credentials provided, running unauthenticated.")
            return False
            
        try:
            self.client.login(username, password)
            self.is_logged_in = True
            logger.info(f"Successfully logged into Instagram as {username}")
            return True
        except Exception as e:
            logger.error(f"Failed to login to Instagram: {e}")
            return False

    def _download_reel_sync(self, url: str, folder: Path) -> Optional[Path]:
        """Synchronous method to download reel using instagrapi"""
        try:
            media_pk = self.client.media_pk_from_url(url)
            # video_download returns the path to the downloaded file
            file_path = self.client.video_download(media_pk, folder=folder)
            
            # Check file size (50MB limit for standard Telegram bots)
            if file_path and file_path.exists():
                file_size_mb = file_path.stat().st_size / (1024 * 1024)
                if file_size_mb > 49.5:  # Slightly less than 50 to be safe
                    logger.warning(f"File too large: {file_size_mb:.2f}MB")
                    file_path.unlink()  # Delete the large file immediately
                    return None
                    
            return file_path
        except ClientError as e:
            logger.error(f"Instagrapi ClientError downloading {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading {url}: {e}")
            return None

    async def download_reel(self, url: str, folder: Path) -> Optional[Path]:
        """Asynchronous wrapper for downloading reels"""
        # Run the synchronous instagrapi logic in a separate thread to not block the bot event loop
        loop = asyncio.get_running_loop()
        file_path = await loop.run_in_executor(None, self._download_reel_sync, url, folder)
        return file_path

# Singleton instance
ig_service = InstagramService()
