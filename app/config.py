from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = Field(
        "postgresql+psycopg://yottaflex:yottaflex@localhost:5432/yottaflex"
    )
    base_currency: str = Field("USD", min_length=3, max_length=3)
    db_pool_size: int = Field(5, ge=1)
    db_max_overflow: int = Field(10, ge=0)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
