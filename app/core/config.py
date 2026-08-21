from functools import lru_cache

from pydantic import Field, SecretStr
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
    document_max_upload_bytes: int = Field(default=25 * 1024 * 1024, alias="DOCUMENT_MAX_UPLOAD_BYTES", gt=0)
    object_storage_endpoint: str = Field(default="http://localhost:9000", alias="OBJECT_STORAGE_ENDPOINT")
    object_storage_bucket: str = Field(default="regbridge-documents", alias="OBJECT_STORAGE_BUCKET")
    object_storage_access_key: str = Field(default="local-access-key", alias="OBJECT_STORAGE_ACCESS_KEY")
    object_storage_secret_key: str = Field(default="local-secret-key", alias="OBJECT_STORAGE_SECRET_KEY")
    object_storage_region: str = Field(default="us-east-1", alias="OBJECT_STORAGE_REGION")
    object_storage_secure: bool = Field(default=False, alias="OBJECT_STORAGE_SECURE")
    object_storage_server_side_encryption: str | None = Field(default=None, alias="OBJECT_STORAGE_SERVER_SIDE_ENCRYPTION")
    clamav_host: str = Field(default="localhost", alias="CLAMAV_HOST")
    clamav_port: int = Field(default=3310, alias="CLAMAV_PORT", gt=0)
    trace_max_payload_bytes: int = Field(default=32768, alias="TRACE_MAX_PAYLOAD_BYTES", gt=0)
    qdrant_url: str | None = Field(default=None, alias="QDRANT_URL")
    qdrant_api_key: SecretStr | None = Field(default=None, alias="QDRANT_API_KEY", repr=False)
    qdrant_collection: str = Field(default="reglementation_chunks", alias="QDRANT_COLLECTION")
    bge_m3_model_name: str = Field(default="BAAI/bge-m3", alias="BGE_M3_MODEL_NAME")
    bge_m3_device: str = Field(default="cpu", alias="BGE_M3_DEVICE")
    mistral_api_key: SecretStr | None = Field(default=None, alias="MISTRAL_API_KEY", repr=False)
    mistral_model: str | None = Field(default=None, alias="MISTRAL_MODEL")

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
