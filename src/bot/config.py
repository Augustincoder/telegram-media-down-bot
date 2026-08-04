from pydantic import field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, Any

class Settings(BaseSettings):
    bot_token: str
    database_url: str = "sqlite+aiosqlite:///bot_database.db"
    
    instagram_username: Optional[str] = None
    instagram_password: Optional[str] = None
    
    # Ikki xil yozilishini ham qabul qiladigan qilib qo'ydik
    instagram_session_id: Optional[str] = Field(default=None, validation_alias="INSTAGRAM_SESSION_ID")
    instagram_sessionid: Optional[str] = Field(default=None, validation_alias="INSTAGRAM_SESSIONID")
    
    admin_ids: List[int] = []

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Any) -> List[int]:
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
        elif isinstance(v, int):
            return [v]
        elif isinstance(v, list):
            return [int(x) for x in v]
        return []

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

config = Settings()
