from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings loaded from the environment or a local .env file."""

    app_name: str = Field(default="RegBridge", alias="APP_NAME")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    database_url: str = Field(alias="DATABASE_URL")
    oidc_issuer: str | None = Field(default=None, alias="OIDC_ISSUER")
    oidc_audience: str | None = Field(default=None, alias="OIDC_AUDIENCE")
    oidc_discovery_url: str | None = Field(default=None, alias="OIDC_DISCOVERY_URL")
    oidc_algorithms: str = Field(default="RS256", alias="OIDC_ALGORITHMS")

    @property
    def allowed_oidc_algorithms(self) -> list[str]:
        return [algorithm.strip() for algorithm in self.oidc_algorithms.split(",") if algorithm.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
