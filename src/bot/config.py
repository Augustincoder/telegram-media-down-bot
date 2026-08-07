from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str = Field(
        validation_alias=AliasChoices("POSTGRES_URL", "DATABASE_URL"),
    )

    instagram_username: str | None = None
    instagram_password: str | None = None

    # Har qanday env o'zgaruvchini avtomatik tutib oladi
    instagram_session_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INSTAGRAM_SESSION_ID", "INSTAGRAM_SESSIONID"),
    )

    storage_channel_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("STORAGE_CHANNEL_ID", "DUMP_CHANNEL_ID"),
    )

    # Telegram Userbot settings
    telegram_api_id: int | None = None
    telegram_api_hash: str | None = None
    telegram_userbot_session_string: str | None = None

    admin_ids: list[int] = []

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Any) -> list[int]:
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
        elif isinstance(v, int):
            return [v]
        elif isinstance(v, list):
            return [int(x) for x in v]
        return []

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


config = Settings()
