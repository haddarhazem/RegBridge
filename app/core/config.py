from functools import lru_cache

from typing import Literal

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
    oidc_client_id: str | None = Field(default=None, alias="OIDC_CLIENT_ID")
    oidc_redirect_uri: str | None = Field(default=None, alias="OIDC_REDIRECT_URI")
    oidc_post_logout_redirect_uri: str | None = Field(default=None, alias="OIDC_POST_LOGOUT_REDIRECT_URI")
    oidc_scope: str = Field(default="openid profile email", alias="OIDC_SCOPE")
    oidc_authorization_audience: str | None = Field(default=None, alias="OIDC_AUTHORIZATION_AUDIENCE")
    oidc_resource: str | None = Field(default=None, alias="OIDC_RESOURCE")
    document_max_upload_bytes: int = Field(default=25 * 1024 * 1024, alias="DOCUMENT_MAX_UPLOAD_BYTES", gt=0)
    object_storage_endpoint: str = Field(default="http://localhost:19000", alias="OBJECT_STORAGE_ENDPOINT")
    object_storage_bucket: str = Field(default="regbridge-documents", alias="OBJECT_STORAGE_BUCKET")
    object_storage_access_key: str = Field(default="local-access-key", alias="OBJECT_STORAGE_ACCESS_KEY")
    object_storage_secret_key: str = Field(default="local-secret-key", alias="OBJECT_STORAGE_SECRET_KEY")
    object_storage_region: str = Field(default="us-east-1", alias="OBJECT_STORAGE_REGION")
    object_storage_secure: bool = Field(default=False, alias="OBJECT_STORAGE_SECURE")
    object_storage_server_side_encryption: str | None = Field(default=None, alias="OBJECT_STORAGE_SERVER_SIDE_ENCRYPTION")
    clamav_host: str = Field(default="localhost", alias="CLAMAV_HOST")
    clamav_port: int = Field(default=3310, alias="CLAMAV_PORT", gt=0)
    trace_max_payload_bytes: int = Field(default=32768, alias="TRACE_MAX_PAYLOAD_BYTES", gt=0)
    copilot_diagnostics_enabled: bool = Field(default=False, alias="COPILOT_DIAGNOSTICS_ENABLED")
    qdrant_url: str | None = Field(default=None, alias="QDRANT_URL")
    qdrant_api_key: SecretStr | None = Field(default=None, alias="QDRANT_API_KEY", repr=False)
    qdrant_collection: str = Field(default="reglementation_chunks", alias="QDRANT_COLLECTION")
    bge_m3_model_name: str = Field(default="BAAI/bge-m3", alias="BGE_M3_MODEL_NAME")
    bge_m3_device: str = Field(default="cpu", alias="BGE_M3_DEVICE")
    regulatory_warmup_on_startup: bool = Field(default=False, alias="REGULATORY_WARMUP_ON_STARTUP")
    mistral_api_key: SecretStr | None = Field(default=None, alias="MISTRAL_API_KEY", repr=False)
    mistral_model: str | None = Field(default=None, alias="MISTRAL_MODEL")
    mistral_ocr_model: str = Field(default="mistral-ocr-latest", alias="MISTRAL_OCR_MODEL")
    llm_provider: Literal["mistral", "deepseek", "ollama", "gemini"] = Field(default="mistral", alias="LLM_PROVIDER")
    deepseek_api_key: SecretStr | None = Field(default=None, alias="DEEPSEEK_API_KEY", repr=False)
    deepseek_model: str = Field(default="deepseek-v4-flash", alias="DEEPSEEK_MODEL")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    ollama_api_key: SecretStr | None = Field(default=None, alias="OLLAMA_API_KEY", repr=False)
    ollama_model: str = Field(default="gpt-oss:20b", alias="OLLAMA_MODEL")
    ollama_base_url: str = Field(default="https://ollama.com/api", alias="OLLAMA_BASE_URL")
    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY", repr=False)
    gemini_model: str = Field(default="gemini-3.8-flash", alias="GEMINI_MODEL")
    gemini_max_attempts: int = Field(default=3, alias="GEMINI_MAX_ATTEMPTS", ge=1, le=5)
    gemini_retry_base_seconds: float = Field(default=3.0, alias="GEMINI_RETRY_BASE_SECONDS", ge=0.1, le=30)
    gemini_retry_max_seconds: float = Field(default=30.0, alias="GEMINI_RETRY_MAX_SECONDS", ge=0.1, le=60)
    gemini_max_total_wait_seconds: float = Field(default=90.0, alias="GEMINI_MAX_TOTAL_WAIT_SECONDS", ge=1, le=300)
    gemini_min_request_interval_seconds: float = Field(default=12.5, alias="GEMINI_MIN_REQUEST_INTERVAL_SECONDS", ge=0, le=60)
    regulatory_generation_max_tokens: int = Field(default=900, ge=1, le=4000, alias="REGULATORY_GENERATION_MAX_TOKENS")
    regulatory_verification_max_tokens: int = Field(default=900, ge=1, le=4000, alias="REGULATORY_VERIFICATION_MAX_TOKENS")
    authoritative_source_fallback_enabled: bool = Field(default=False, alias="AUTHORITATIVE_SOURCE_FALLBACK_ENABLED")
    document_external_processing_enabled: bool = Field(default=False, alias="DOCUMENT_EXTERNAL_PROCESSING_ENABLED")
    document_native_text_min_chars: int = Field(default=32, alias="DOCUMENT_NATIVE_TEXT_MIN_CHARS", ge=1)
    document_extraction_stale_after_seconds: int = Field(default=900, alias="DOCUMENT_EXTRACTION_STALE_AFTER_SECONDS", gt=0)
    document_extraction_max_attempts: int = Field(default=3, alias="DOCUMENT_EXTRACTION_MAX_ATTEMPTS", ge=1, le=10)
    document_extraction_concurrency: int = Field(default=2, alias="DOCUMENT_EXTRACTION_CONCURRENCY", ge=1, le=16)

    @property
    def allowed_oidc_algorithms(self) -> list[str]:
        return [algorithm.strip() for algorithm in self.oidc_algorithms.split(",") if algorithm.strip()]

    @property
    def copilot_developer_diagnostics_enabled(self) -> bool:
        return self.environment.lower() == "development" or self.copilot_diagnostics_enabled

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
