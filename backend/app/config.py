from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = (
        "postgresql+psycopg://banking:local-demo-database-only@localhost:5433/banking"
    )
    jwt_secret: str = Field(min_length=32)
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    cookie_secure: bool = False
    access_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    refresh_days: int = Field(default=7, ge=1, le=30)
    docs_enabled: bool = True
    transfer_min_vnd: int = Field(default=1, ge=1, le=9007199254740991)
    transfer_max_vnd: int = Field(default=9007199254740991, ge=1, le=9007199254740991)

    @model_validator(mode="after")
    def valid_transfer_bounds(self):
        if self.transfer_min_vnd > self.transfer_max_vnd:
            raise ValueError("Minimum transfer amount cannot exceed maximum.")
        return self

    @property
    def origins(self) -> list[str]:
        return self.allowed_origins.split(",")


@lru_cache
def settings() -> Settings:
    return Settings()
