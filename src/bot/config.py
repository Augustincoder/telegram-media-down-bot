from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    bot_token: str
    database_url: str = "sqlite+aiosqlite:///bot_database.db"
    
    instagram_username: Optional[str] = None
    instagram_password: Optional[str] = None
    
    admin_ids: List[int] = []

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

config = Settings()
