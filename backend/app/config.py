from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        extra="ignore",
    )

    database_url: str
    jwt_secret: str = Field(min_length=32)
    app_origins: str = "http://localhost:5173,http://localhost:8000"
    cookie_secure: bool = False
    jwt_ttl_hours: int = Field(default=24, ge=1, le=168)
    judge_enabled: bool = False

    @property
    def allowed_origins(self) -> set[str]:
        return {origin.strip().rstrip("/") for origin in self.app_origins.split(",") if origin.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
