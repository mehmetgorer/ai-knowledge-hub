from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

from ai_knowledge_hub_api.auth.errors import AuthenticationConfigurationError
from ai_knowledge_hub_api.auth.jwks import validate_auth_jwks_url

_PACKAGE_DIR = Path(__file__).resolve().parent
_API_ROOT = _PACKAGE_DIR.parent.parent
_REPO_ROOT = _API_ROOT.parent.parent

_ENV_FILES = (
    _REPO_ROOT / ".env",
    _API_ROOT / ".env",
)


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=tuple(str(path) for path in _ENV_FILES if path.is_file())
        or (str(_API_ROOT / ".env"),),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(
        default="ai-knowledge-hub-api",
        validation_alias="SERVICE_NAME",
    )
    cors_origins_raw: str = Field(
        default="http://localhost:3000",
        validation_alias="CORS_ORIGINS",
    )
    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")

    database_url: SecretStr | None = Field(
        default=None,
        validation_alias="DATABASE_URL",
    )
    postgres_db: str = Field(
        default="ai_knowledge_hub",
        validation_alias="POSTGRES_DB",
    )
    postgres_user: str = Field(
        default="ai_knowledge_hub",
        validation_alias="POSTGRES_USER",
    )
    postgres_password: SecretStr = Field(
        default=SecretStr("dev_password_change_me"),
        validation_alias="POSTGRES_PASSWORD",
    )
    postgres_host: str = Field(default="127.0.0.1", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5433, validation_alias="POSTGRES_PORT")
    database_connect_timeout: float = Field(
        default=5.0,
        validation_alias="DATABASE_CONNECT_TIMEOUT",
    )

    auth_jwks_url: str | None = Field(
        default=None,
        validation_alias="AUTH_JWKS_URL",
    )
    auth_issuer: str | None = Field(
        default=None,
        validation_alias="AUTH_ISSUER",
    )
    auth_audience: str | None = Field(
        default=None,
        validation_alias="AUTH_AUDIENCE",
    )
    auth_jwks_cache_ttl_seconds: float = Field(
        default=300.0,
        validation_alias="AUTH_JWKS_CACHE_TTL_SECONDS",
    )
    auth_jwks_request_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="AUTH_JWKS_REQUEST_TIMEOUT_SECONDS",
    )

    document_storage_root: str = Field(
        default="var/document_storage",
        validation_alias="DOCUMENT_STORAGE_ROOT",
    )
    document_max_upload_bytes: int = Field(
        default=10 * 1024 * 1024,
        validation_alias="DOCUMENT_MAX_UPLOAD_BYTES",
    )

    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        validation_alias="OLLAMA_BASE_URL",
    )
    ollama_model: str = Field(
        default="qwen3:1.7b",
        validation_alias="OLLAMA_MODEL",
    )
    ollama_request_timeout_seconds: float = Field(
        default=120.0,
        validation_alias="OLLAMA_REQUEST_TIMEOUT_SECONDS",
    )
    rag_max_evidence_passages: int = Field(
        default=5,
        validation_alias="RAG_MAX_EVIDENCE_PASSAGES",
    )
    rag_max_evidence_characters: int = Field(
        default=12_000,
        validation_alias="RAG_MAX_EVIDENCE_CHARACTERS",
    )
    rag_max_output_tokens: int = Field(
        default=512,
        validation_alias="RAG_MAX_OUTPUT_TOKENS",
    )

    @field_validator("ollama_base_url")
    @classmethod
    def _validate_ollama_base_url(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("OLLAMA_BASE_URL must not be empty")
        if not stripped.startswith(("http://", "https://")):
            raise ValueError("OLLAMA_BASE_URL must be an http(s) URL")
        return stripped.rstrip("/")

    @field_validator("auth_jwks_url")
    @classmethod
    def _validate_auth_jwks_url(cls, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        return validate_auth_jwks_url(str(value).strip())

    @field_validator("auth_issuer", "auth_audience", mode="before")
    @classmethod
    def _empty_auth_string_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def require_auth_configuration(self) -> None:
        if not self.auth_jwks_url or not self.auth_issuer:
            raise AuthenticationConfigurationError(
                "AUTH_JWKS_URL and AUTH_ISSUER must be configured for protected routes"
            )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        origins = [
            item.strip() for item in self.cors_origins_raw.split(",") if item.strip()
        ]
        return origins or ["http://localhost:3000"]

    @property
    def resolved_database_url(self) -> str:
        if self.database_url is not None:
            return self.database_url.get_secret_value()
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    @property
    def resolved_document_storage_root(self) -> Path:
        path = Path(self.document_storage_root)
        if not path.is_absolute():
            path = _API_ROOT / path
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
