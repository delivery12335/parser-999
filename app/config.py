from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = ""
    check_interval: int = Field(default=300, ge=30)
    database_url: str = "sqlite+aiosqlite:///apartments.db"
    android_api_token: str = ""
    call_mode: Literal["iphone", "android"] = "iphone"
    server_host: str = "0.0.0.0"
    server_port: int = Field(default=8000, ge=1, le=65535)
    public_base_url: str = "https://your-domain.example"
    search_url: str = (
        "https://999.md/ru/list/real-estate/apartments-and-rooms"
        "?sort_type=date_desc&o_16_1=912"
    )
    request_timeout: float = Field(default=20.0, gt=0)
    parser_pages: int = Field(default=2, ge=1, le=10)
    user_agent: str = "ApartmentWatcher/1.0 (+personal, low-frequency public-page monitor)"
    log_level: str = "INFO"

    @field_validator("android_api_token")
    @classmethod
    def token_is_present_in_production(cls, value: str) -> str:
        return value.strip()

    @property
    def sqlite_path(self) -> Path | None:
        prefix = "sqlite+aiosqlite:///"
        return Path(self.database_url.removeprefix(prefix)) if self.database_url.startswith(prefix) else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
